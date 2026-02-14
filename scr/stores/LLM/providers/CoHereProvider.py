from ..LLMInterface import LLMInterface
from ..LLMEnums import CoHereEnums,DocumentTypeEnum
import time, random
import cohere
import logging
from typing import List , Union

class CoHereProvider(LLMInterface):
     def __init__(
              self, api_key: str,
              default_input_max_characters:int=1000,
              default_out_put_max_characters:int=1000,
              default_generation_temperature:float =0.1

            ):
        self.api_key = api_key
        self.default_input_max_characters=default_input_max_characters
        self.default_out_put_max_characters=default_out_put_max_characters
        self.default_generation_temperature=default_generation_temperature

        self.generate_model_id =None

        self.embedding_model_id=None
        self.embedding_size=None


        self.client =cohere.Client(api_key=self.api_key)
        self.logger=logging.getLogger(__name__)
        self.enums =CoHereEnums



     def set_generation_model(self,model_id:str):
            self.generate_model_id=model_id
    
     def set_embedding_model(self,model_id:str,embedding_size:int): 
            self.embedding_model_id =model_id
            self.embedding_size = embedding_size
    

     def process_text(self,text:str):
            return text[:self.default_input_max_characters].strip()
     

     def generate_text(self,prompt:str,max_output_tokens:int=4000,chat_history=None,temperature:float=None):
         
        if not self.client:
            self.logger.error("CoHere Client was not set")
            return None
        
        if not self.generate_model_id:
            self.logger.error("Generation model for CoHere was not set")
            return None
        max_output_tokens = max_output_tokens if max_output_tokens  else self.default_out_put_max_characters

        temperature = temperature if temperature else self.default_generation_temperature
        
        # Normalize chat history to Cohere's expected shape: [{"role": ..., "message": ...}]
        normalized_history = None
        if isinstance(chat_history, list) and len(chat_history) > 0:
            try:
                temp_history = []
                for item in chat_history:
                    if not isinstance(item, dict):
                        continue
                    role = item.get("role")
                    # Accept either 'content' (internal) or 'message' (Cohere)
                    message = item.get("message") if item.get("message") is not None else item.get("content")
                    if role and message:
                        temp_history.append({"role": role, "message": message})
                normalized_history = temp_history if len(temp_history) > 0 else None
            except Exception:
                normalized_history = None

        # Don't truncate the main prompt - send it as-is for RAG scenarios
        # The prompt may contain retrieved documents and should be sent completely
        self.logger.info(f"Prompt length: {len(prompt)} characters (sent without truncation)")
        
        response= self.client.chat(
             model = self.generate_model_id,
             chat_history=normalized_history,
             message= prompt,  # Send full prompt without truncation
             temperature =temperature,
             max_tokens=max_output_tokens
        )
        if not response or not response.text:
             self.logger.error("Error while generating text with CoHere")
             return None
        return response.text


     def embed_text(self, texts:Union[str,List[str]], document_type: str = None, batch_size: int = 32, max_retries: int = 5):
          if not self.client:
               self.logger.error("CoHere client was not set")
               return None
          if not self.embedding_model_id:
               self.logger.error("Embedding model for CoHere was not set")
               return None

          # Determine input type (document or query)
          input_type = CoHereEnums.DOCUMENT.value
          if document_type == DocumentTypeEnum.QUERY.value:
               input_type = CoHereEnums.QUERY.value

          # Ensure input is always a list
          if isinstance(texts, str):
               texts = [texts]

          # Preprocess all texts before sending
          processed_texts = [self.process_text(t) for t in texts]

          all_vectors = []

          # Split into batches
          for i in range(0, len(processed_texts), batch_size):
               batch = processed_texts[i:i+batch_size]

               retries = 0
               while retries < max_retries:
                    try:
                         response = self.client.embed(
                              model=self.embedding_model_id,
                              texts=batch,
                              input_type=input_type,
                              embedding_types=['float'],
                         )

                         if not response or not getattr(response, "embeddings", None):
                              self.logger.error("Empty response from Cohere embeddings")
                              break

                         embeddings_obj = response.embeddings

                         # v5 path
                         float_vectors = getattr(embeddings_obj, "float", None)
                         if isinstance(float_vectors, list) and len(float_vectors) > 0:
                              all_vectors.extend(float_vectors)
                              break

                         # fallback paths
                         if isinstance(embeddings_obj, list) and len(embeddings_obj) > 0:
                              for candidate in embeddings_obj:
                                   for attr in ("values", "embedding", "float", "data"):
                                        vec = getattr(candidate, attr, None)
                                        if isinstance(vec, list) and len(vec) > 0:
                                             all_vectors.append(vec)
                                             break
                              break

                         self.logger.error("Could not parse embeddings for batch")
                         break

                    except Exception as e:
                         if "429" in str(e):
                              wait = (2 ** retries) + random.random()
                              self.logger.warning(f"Rate limited. Retrying in {wait:.2f} sec...")
                              time.sleep(wait)
                              retries += 1
                              continue
                         else:
                              self.logger.error(f"Exception during Cohere embedding request: {e}")
                              break

          if not all_vectors:
               self.logger.error("Failed to get any embeddings")
               return None

          return all_vectors

     

     

     def construct_prompt(self,prompt:str,role:str):
        return{
            "role":role,
            "content":prompt
        }




