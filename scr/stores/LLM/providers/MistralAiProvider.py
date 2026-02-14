from stores.LLM.LLMInterface import LLMInterface
from stores.LLM.LLMEnums import OpenAIEnums
from openai import OpenAI
import logging
from typing import List , Union


class OpenAIProvider(LLMInterface):
    """
    OpenAIProvider: Wrapper class for interacting with LLM APIs
    -----------------------------------------------------------
    This class is designed to interact with OpenAI API or any 
    OpenAI-compatible API endpoint (e.g., Ollama, vLLM, custom proxy).

    Parameters
    ----------
    api_key : str
        The authentication key for the API.
        - For OpenAI Cloud: use your real OpenAI API key.
        - For local servers (like Ollama): you can pass a dummy value (not required).

    api_url : str, optional
        Base URL of the API endpoint.
        - Default for OpenAI: "https://api.openai.com/v1"
        - For Ollama local server: "http://localhost:11434/v1"
        - For custom proxies: provide the proxy endpoint.
    """

    def __init__(
              self, api_key: str,
              api_url: str = None,
              default_input_max_characters:int=1000,
              default_out_put_max_characters:int=1000,
              default_generation_temperature:float =0.1

            ):
        self.api_key = api_key
        self.api_url = api_url 
        self.default_input_max_characters=default_input_max_characters
        self.default_out_put_max_characters=default_out_put_max_characters
        self.default_generation_temperature=default_generation_temperature

        self.generate_model_id =None

        self.embedding_model_id=None
        self.embedding_model_size=None

        self.client =OpenAI(
            api_key = self.api_key,
            base_url=self.api_url if self.api_url and len(self.api_url) else None
        )

        self.enums=OpenAIEnums

        
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self,model_id:str):
        self.generate_model_id=model_id
    
    def set_embedding_model(self,model_id:str,embedding_size:int):
        self.embedding_model_id =model_id
        self.embedding_model_size = embedding_size


    def process_text(self,text:str):
        return text[:self.default_input_max_characters].strip()
        

    def generate_text(self,prompt:str,max_output_tokens:int=1000,chat_history:list=[],temperature:float=None):
         
        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return None
        
        if not self.generate_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return None
        max_output_tokens = max_output_tokens if max_output_tokens  else self.default_out_put_max_characters

        temperature = temperature if temperature else self.default_generation_temperature

        chat_history.append(
            self.construct_prompt(prompt=prompt,role=OpenAIEnums.USER.value)
        )

        response = self.client.chat.completions.create(
            model = self.generate_model_id,
            messages=chat_history,
            max_tokens=max_output_tokens,
            temperature=temperature
        )

        if not response or not response.choices or len(response.choices) ==0 or not response.choices[0].messages:
            self.logger.error("Error while generating text with OpenAI")
            return None
        return response.choices[0].message.content




    def embed_text(self,texts:Union[str,List[str]],document_type:str=None):
        
        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model for OpenAI was not set")

        if isinstance(texts,str):
            texts=[texts]
        
        response= self.client.embeddings.create(
            model = self.embedding_model_id,
            input=texts,
        )
        
        if not response or not response.data or len(response.data) == 0 or  not response.data[0].embedding:
            self.logger.error("Error While embedding text with OpenAI")
            return None 
        return [data.embedding for data in response.data]
    def construct_prompt(self,prompt:str,role:str):
        return{
            "role":role,
            "content":prompt
        }

    



        