from .BaseController import BaseController
from .QueryPreprocessor import QueryPreprocessor
from models.db_schems import Project,DataChunk
from stores.LLM.LLMEnums import DocumentTypeEnum
from typing import List
import logging
import json
import time
from starlette.concurrency import run_in_threadpool

class NLPController(BaseController):
    def __init__(self,vectordb_client,generation_client,embedding_client,template_parser):
        super().__init__()

        self.vectordb_client=vectordb_client
        self.generation_client=generation_client
        self.embedding_client=embedding_client
        self.template_parser=template_parser
        self.query_preprocessor = QueryPreprocessor()
        self.logger = logging.getLogger(__name__)
    
    def create_collection_name(self,project_id:str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()
    
    async def reset_vector_db_collection(self,project:Project):
        collection_name=self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name=collection_name)
    
    async def get_vector_db_collection_info(self,project:Project):
        collection_name= self.create_collection_name(project_id=project.project_id)

        collection_info= await self.vectordb_client.get_collection_info(collection_name=collection_name)
        return json.loads(
            json.dumps(collection_info,default=lambda x:x.__dict__)
        )
    
    async def index_into_vector_db(self, project: Project, chunks: List[DataChunk],
                               chunks_ids: List[int], 
                               do_reset: bool = False):
        # step1: get collection name
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: manage items
        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]

        try:
            vectors = self.embedding_client.embed_text(
                texts=texts, 
                document_type=DocumentTypeEnum.DOCUMENT.value
            )
        except Exception as e:
            self.logger.error(f"Embedding generation failed: {e}")
            return False

        # sanity checks
        if not vectors or len(vectors) != len(texts):
            self.logger.error(
                f"Embedding mismatch: got {len(vectors) if vectors else 0} vectors for {len(texts)} texts"
            )
            return False

        assert len(vectors) == len(chunks_ids), f"Vectors ({len(vectors)}) != IDs ({len(chunks_ids)})"
        assert len(vectors) == len(metadata), f"Vectors ({len(vectors)}) != Metadata ({len(metadata)})"
        assert all(isinstance(i, int) for i in chunks_ids), "All record_ids must be int"

        # step3: create collection if not exists
        await self.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # step4: insert into vector db
        insertion_result = await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunks_ids,
        )

        if insertion_result:
            self.logger.info(f"Successfully indexed {len(vectors)} chunks into collection '{collection_name}'")
        else:
            self.logger.error(f"Failed to insert vectors into collection '{collection_name}'")

        return insertion_result

    
    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 3):

        # step1: get collection name
        query_vector = None
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step2: get text embedding vector
        vectors = self.embedding_client.embed_text(texts=[text], 
                                                 document_type=DocumentTypeEnum.QUERY.value)

        if not vectors or len(vectors) == 0:
            return False
        
        if isinstance(vectors, list) and len(vectors) > 0:
            query_vector = vectors[0]

        if not query_vector:
            return False    

        # step3: do semantic search
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        if not results:
            return False

        return results

    async def answer_rag_question(self,project:Project,query:str,limit:int=3, ui_context: List[str] = None):
        answer,full_prompt,chat_history = None,None,None
        
        # Timing instrumentation
        t_start = time.time()

        # Preprocess the query
        t_preprocess_start = time.time()
        preprocessed = self.query_preprocessor.preprocess_query(query)
        t_preprocess = time.time() - t_preprocess_start
        
        # If it's a greeting, return the greeting response
        if preprocessed['is_greeting']:
            return preprocessed['greeting_response'], None, None
        
        # Use normalized query for retrieval
        normalized_query = preprocessed['normalized_query']
        is_detail_request = preprocessed['is_detail_request']

        t_search_start = time.time()
        retrived_documents = await self.search_vector_db_collection(
            project=project,
            text=normalized_query,
            limit=limit
        )
        t_search_end = time.time()

        if not retrived_documents or len(retrived_documents)==0:
            return  answer,full_prompt,chat_history
        

       

        # Choose appropriate system prompt based on detail request
        t_prompt_build_start = time.time()
        if is_detail_request:
            system_prompt=self.template_parser.get("rag","system_prompt_detailed")
        else:
            system_prompt=self.template_parser.get("rag","system_prompt")

        documents_prompts="\n".join([
                self.template_parser.get("rag","document_type",{
                    "doc_num": idx+1,
                    "chunk_text":self.generation_client.process_text(doc.text),

                })
                for idx,doc in enumerate(retrived_documents)

            ])

        # Append UI context if provided
        if ui_context:
            ui_blocks = []
            for ui_idx, ui_text in enumerate(ui_context):
                ui_blocks.append(
                    self.template_parser.get(
                        "rag",
                        "document_type",
                        {
                            "doc_num": len(retrived_documents) + ui_idx + 1,
                            "chunk_text": self.generation_client.process_text(str(ui_text)),
                        },
                    )
                )
            if ui_blocks:
                documents_prompts = "\n".join([documents_prompts, "\n".join(ui_blocks)])

        # Choose appropriate footer prompt based on detail request
        if is_detail_request:
            footer_prompt=self.template_parser.get("rag","footer_prompt_detailed")
        else:
            footer_prompt=self.template_parser.get("rag","footer_prompt")

        chat_history=[
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,

            )
        ]
        
        # Include the user's question in the prompt
        user_question_section = f"## السؤال:\n{normalized_query}\n\n"
        full_prompt = "\n\n".join([documents_prompts, user_question_section, footer_prompt])
        t_prompt_build_end = time.time()

        try:
            # generation_client.generate_text_streaming is a blocking generator (network I/O).
            # Run it in a threadpool to avoid blocking the async event loop.
            t_generation_start = time.time()
            
            # This returns a generator that yields chunks
            def get_streaming_generator():
                return self.generation_client.generate_text_streaming(
                    prompt=full_prompt,
                    max_output_tokens=2000,
                    chat_history=chat_history,
                )
            
            # Run in threadpool and collect the full answer
            answer_parts = []
            async def collect_streaming_response():
                gen = await run_in_threadpool(get_streaming_generator)
                for chunk in gen:
                    if chunk:
                        answer_parts.append(chunk)
                return "".join(answer_parts)
            
            answer = await collect_streaming_response()
            t_generation_end = time.time()

            if not answer:
                self.logger.error("Generation client returned None or empty answer")
            else:
                # Log timing only on success
                t_total = time.time() - t_start
                self.logger.debug(
                    f"[TIMING] Preprocess: {t_preprocess:.2f}s | Search: {t_search_end-t_search_start:.2f}s | "
                    f"Prompt: {t_prompt_build_end-t_prompt_build_start:.2f}s | Generation: {t_generation_end-t_generation_start:.2f}s | Total: {t_total:.2f}s"
                )
                
        except Exception as e:
            self.logger.error(f"Exception during text generation: {e}", exc_info=True)
            answer = None

        return answer,full_prompt,chat_history
    
    async def answer_rag_question_streaming(self, project: Project, query: str, limit: int = 3, ui_context: List[str] = None):
        """
        Streaming version that yields answer chunks as they arrive.
        For use with Server-Sent Events (SSE).
        """
        # Preprocess the query
        preprocessed = self.query_preprocessor.preprocess_query(query)
        
        # If it's a greeting, return immediately
        if preprocessed['is_greeting']:
            yield f"data: {json.dumps({'type': 'chunk', 'content': preprocessed['greeting_response']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        
        normalized_query = preprocessed['normalized_query']
        is_detail_request = preprocessed['is_detail_request']

        # Search vector DB
        retrived_documents = await self.search_vector_db_collection(
            project=project,
            text=normalized_query,
            limit=limit
        )

        if not retrived_documents or len(retrived_documents) == 0:
            yield f"data: {json.dumps({'type': 'error', 'content': 'لم يتم العثور على نتائج'})}\n\n"
            return

        # Build prompts
        if is_detail_request:
            system_prompt = self.template_parser.get("rag", "system_prompt_detailed")
        else:
            system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_type", {
                "doc_num": idx + 1,
                "chunk_text": self.generation_client.process_text(doc.text),
            })
            for idx, doc in enumerate(retrived_documents)
        ])

        if is_detail_request:
            footer_prompt = self.template_parser.get("rag", "footer_prompt_detailed")
        else:
            footer_prompt = self.template_parser.get("rag", "footer_prompt")

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        user_question_section = f"## السؤال:\n{normalized_query}\n\n"
        full_prompt = "\n\n".join([documents_prompts, user_question_section, footer_prompt])

        try:
            # Get streaming generator
            def get_streaming_gen():
                return self.generation_client.generate_text_streaming(
                    prompt=full_prompt,
                    max_output_tokens=2000,
                    chat_history=chat_history,
                )
            
            gen = await run_in_threadpool(get_streaming_gen)
            
            # Yield chunks as SSE events
            for chunk in gen:
                if chunk:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            self.logger.error(f"Error during streaming: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': 'حدث خطأ أثناء معالجة السؤال'})}\n\n"

       




    




    