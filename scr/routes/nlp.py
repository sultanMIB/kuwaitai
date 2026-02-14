from fastapi import APIRouter,FastAPI, Depends,UploadFile,status,Request
from fastapi.responses import JSONResponse, StreamingResponse
from helper.config import get_settings
from routes.Schemas.nlp import PushRequest, SearchRequest
from models import ResponseStatus
from models.ChunkModel import ChunkModel
from models.ProjectModel import ProjectModel
from tqdm.auto import tqdm

from controllers import NLPController

import logging
import json

logger=logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)

nlp_router = APIRouter(
    prefix="/nlp",
    tags=["nlp"],
    responses={404: {"description": "Not found"}},
)

# Helpers
def _extract_project_id_from_collection_name(name: str):
    prefix = "collection_"
    if name.startswith(prefix):
        return name[len(prefix):]
    return None

async def _resolve_student_project_id(request: Request):
    settings = get_settings()
    # Prefer last available indexed project by looking at existing collections
    try:
        collections = await request.app.vectordb_client.list_all_collection()
        # qdrant get_collections returns an object; normalize to names list
        names = []
        if hasattr(collections, "collections") and isinstance(collections.collections, list):
            for c in collections.collections:
                name = getattr(c, "name", None) or (c.get("name") if isinstance(c, dict) else None)
                if isinstance(name, str):
                    names.append(name)
        elif isinstance(collections, list):
            names = [c.get("name") if isinstance(c, dict) else getattr(c, "name", None) for c in collections]
            names = [n for n in names if isinstance(n, str)]

        candidates = [n for n in names if isinstance(n, str) and n.startswith("collection_")]
        if candidates:
            candidates.sort()  # heuristic: pick lexicographically last
            last_name = candidates[-1]
            pid = _extract_project_id_from_collection_name(last_name)
            if pid:
                return pid
    except Exception:
        pass
    # fallback to default
    return settings.DEFAULT_PROJECT_ID

async def _ensure_collection_exists(request: Request, project_id: str):
    controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=getattr(request.app, "template_parser", None)
    )
    collection_name = controller.create_collection_name(project_id=project_id)
    exists = await request.app.vectordb_client.is_collection_existed(collection_name)
    if not exists:
        await request.app.vectordb_client.create_collection(
            collection_name=collection_name,
            embedding_size=request.app.embedding_client.embedding_size,
            do_reset=False,
        )

@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request,project_id:int,push_request:PushRequest):


    chunk_model= await ChunkModel.create_instance(
        db_client=request.app.db_client
    )

    
    projectmodel = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project= await projectmodel.get_project_or_create_one(
        project_id=project_id
    ) 

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message" : ResponseStatus.PROJECT_NOT_FOUND_ERORR.value
            }
        )
    nlp_controller=NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    has_records=True
    page_no=1
    inserted_items_count =0
    idx=0

    collection_name= nlp_controller.create_collection_name(project_id=project.project_id)

    _= await request.app.vectordb_client.create_collection(
        collection_name=collection_name,
        embedding_size= request.app.embedding_client.embedding_size,
        do_reset=push_request.do_reset,
    )

    # If do_reset=1, index all chunks; otherwise only index unindexed ones
    if push_request.do_reset == 1:
        total_chunks_count = await chunk_model.get_total_chunks_count(project_id=project.project_id)
        get_chunks_method = chunk_model.get_project_chunks
    else:
        total_chunks_count = await chunk_model.get_total_unindexed_chunks_count(project_id=project.project_id)
        get_chunks_method = chunk_model.get_unindexed_project_chunks

    pbar = tqdm(total=total_chunks_count, desc="Vector Indexing", position=0)

    while has_records:
        page_chunks = await get_chunks_method(project_id=project.project_id, page_no=page_no)

        if not page_chunks or len(page_chunks)==0:
            has_records = False
            break
        chunks_ids=[c.chunk_id for c in page_chunks]
        idx += len(page_chunks)
        is_inserted = await nlp_controller.index_into_vector_db(
            project=project,
            chunks=page_chunks,
            chunks_ids=chunks_ids,
        )

        if not is_inserted:
            logger.error(f"Failed to insert chunks from page {page_no} for project {project_id}")
            return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message" : ResponseStatus.INSERT_INTO_VECTORDB_ERORR.value
            }
        )
        
        # Mark chunks as indexed (only if not doing full reset)
        if push_request.do_reset != 1:
            await chunk_model.mark_chunks_as_indexed(chunks_ids)
        
        pbar.update(len(page_chunks))
        inserted_items_count +=len(page_chunks)
        logger.info(f"Inserted {len(page_chunks)} chunks from page {page_no}, total so far: {inserted_items_count}")
        page_no += 1


    logger.info(f"Successfully inserted {inserted_items_count} chunks for project {project_id}")
    return JSONResponse(
            content={
                "message": ResponseStatus.INSERT_INTO_VECTORDB_SUCCESS.value,
                "inserted_items_count": inserted_items_count
            }
        )
    
@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request:Request,project_id:int):


    projectmodel = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

    project= await projectmodel.get_project_or_create_one(
        project_id=project_id
    ) 


    nlp_controller=NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser= request.app.template_parser

    )

    collection_info= await nlp_controller.get_vector_db_collection_info(project=project)
    return JSONResponse(
            content={
                "message": ResponseStatus.VECTOR_DB_COLLECTION_RETRIEVED.value,
                "collection_info": collection_info
            }
        )



@nlp_router.post("/index/search/{project_id}")
async def search_index(request:Request, project_id:int, search_request:SearchRequest):
        projectmodel = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

        project= await projectmodel.get_project_or_create_one(
        project_id=project_id
    ) 


        nlp_controller=NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser= request.app.template_parser
    )
        
        query_text = search_request.question if search_request.question is not None else search_request.text
        results= await nlp_controller.search_vector_db_collection(
             project=project,
             text=query_text,limit=search_request.limit
        )

        if not results :
             return JSONResponse(
            content={
                "message": ResponseStatus.ERORR_WITH_SEARCH_BY_VECTOR.value,
            }
        )
       
        return JSONResponse(
            content={
                "message": ResponseStatus.SUCCESS_WITH_SEARCH_BY_VECTOR.value,
                "results":[ result.dict()  for result in results ]
            }
        )



@nlp_router.post("/index/answer/{project_id}")
async def answer_index(request:Request, project_id:int, search_request:SearchRequest):
        projectmodel = await ProjectModel.create_instance(
        db_client=request.app.db_client
    )

        project= await projectmodel.get_project_or_create_one(
        project_id=project_id
    ) 


        nlp_controller=NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client= request.app.embedding_client,
        template_parser=request.app.template_parser
    )
        

        answer , full_prompt , chat_history= await nlp_controller.answer_rag_question(
             project=project,
             query=search_request.text,
             limit= search_request.limit
        )

        # Handle greeting responses
        if answer and not full_prompt and not chat_history:
            return JSONResponse(
                content={
                    "message": "GREETING_RESPONSE",
                    "answer": answer,
                    "is_greeting": True,
                    "full_prompt": None,
                    "chat_history": None
                }
            )

        if not answer :
             return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message" : ResponseStatus.ERORR_ANSWER.value
            }
        )
        return JSONResponse(
            content={
                "message" : ResponseStatus.ANSWER_SUCCESS.value,
                "answer":answer,
                "full_prompt":full_prompt,
                "chat_history":chat_history,
                "is_greeting": False
            }
        )


@nlp_router.post("/chat/answer")
async def chat_answer(request:Request, search_request:SearchRequest):
    async def incremental_generator():
        # start (server-only)
        logger.info('step: start')

        # Resolve project id
        try:
            project_id = await _resolve_student_project_id(request)
            logger.info(f'step: project_resolved:{project_id}')
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'error resolving project_id: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Create/get project
        try:
            projectmodel = await ProjectModel.create_instance(db_client=request.app.db_client)
            project = await projectmodel.get_project_or_create_one(project_id=project_id)
            logger.info('step: project_ready')
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'error getting/creating project: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Ensure collection exists
        try:
            await _ensure_collection_exists(request, project_id)
            logger.info('step: collection_ready')
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'error ensuring collection: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Instantiate controller
        try:
            nlp_controller = NLPController(
                vectordb_client=request.app.vectordb_client,
                generation_client=request.app.generation_client,
                embedding_client=request.app.embedding_client,
                template_parser=request.app.template_parser,
            )
            logger.info('step: controller_ready')
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'error creating controller: {str(e)}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Validate question
        question_text = search_request.question if search_request.question is not None else search_request.text
        if not question_text:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Question is required'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        logger.info('step: starting_generation')

        # Stream actual generation from controller
        try:
            async for event in nlp_controller.answer_rag_question_streaming(
                project=project,
                query=question_text,
                limit=search_request.limit or 3,
                ui_context=None,
            ):
                yield event

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'error during generation: {str(e)}'})}\n\n"

        # done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(incremental_generator(), media_type="text/event-stream")
        

        
             









