from ..LLMInterface import LLMInterface
from ..LLMEnums import OpenAIEnums
from openai import OpenAI
import logging
from typing import List, Union, Dict
import tiktoken
from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptDebugInfo:
    system_prompt_tokens: int
    user_question_tokens: int
    chunk_tokens: List[int]
    chat_history_tokens: int
    total_tokens: int
    model_max_tokens: int
    completion_max_tokens: int


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
              default_generation_temperature:float = None

            ):
        self.api_key = api_key
        self.api_url = api_url 
        self.default_input_max_characters=default_input_max_characters
        self.default_out_put_max_characters=default_out_put_max_characters
        self.default_generation_temperature=default_generation_temperature

        self.generate_model_id =None
        # debug / tokenizer state
        self.tokenizer = None
        self.debug_mode = True

        self.embedding_model_id=None
        self.embedding_size=None

        self.client =OpenAI(
            api_key = self.api_key,
            base_url=self.api_url if self.api_url and len(self.api_url) else None
        )

        self.enums=OpenAIEnums

        
        self.logger = logging.getLogger(__name__)
    
    def _ensure_tokenizer(self):
        """Ensures tokenizer is initialized for the current model"""
        if not getattr(self, 'tokenizer', None):
            try:
                if self.generate_model_id:
                    # إذا النموذج معروف، حاول استخدام tiktoken.encoding_for_model
                    try:
                        self.tokenizer = tiktoken.encoding_for_model(self.generate_model_id)
                    except Exception:
                        # fallback لنموذج جديد زي gpt-5
                        self.logger.warning(f"Could not map {self.generate_model_id} automatically, using cl100k_base.")
                        self.tokenizer = tiktoken.get_encoding("cl100k_base")
                else:
                    self.tokenizer = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                self.logger.warning(f"Could not initialize tokenizer: {e}. Using basic estimation.")
                self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the model's tokenizer"""
        self._ensure_tokenizer()
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception:
                return int(len(text.split()) * 1.3)
        else:
            # Fallback: rough estimation
            return int(len(text.split()) * 1.3)

    def debug_prompt(self, messages: List[Dict], max_tokens: int):
        """Debug prompt structure and token usage"""
        if not getattr(self, 'debug_mode', False):
            return 0
        
        self._ensure_tokenizer()
        
        # Model context limits (detect by model id substring)
        model_limit = 4096
        if self.generate_model_id:
            gid = str(self.generate_model_id).lower()
            if "gpt-5" in gid:
                # GPT-5 family supports very large contexts (commonly 128k)
                model_limit = 128000
            elif "gpt-4-32k" in gid or "gpt-4-32" in gid:
                model_limit = 32768
            elif "gpt-4" in gid:
                model_limit = 8192
            elif "gpt-3.5" in gid or "gpt-3.5-turbo" in gid:
                model_limit = 4096
            else:
                # unknown model: keep a conservative default
                model_limit = 4096
        
        debug_info = {
            "system_prompt": 0,
            "chat_history": 0,
            "retrieved_chunks": [],
            "user_question": 0
        }
        
        # Analyze each message
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            tokens = self.count_tokens(content)
            
            if role == "system":
                debug_info["system_prompt"] = tokens
            elif role == "user":
                if "## المستند" in content or "## Document" in content or "## Document No" in content:
                    # This is a retrieved chunk
                    debug_info["retrieved_chunks"].append(tokens)
                else:
                    # This is the user question
                    debug_info["user_question"] = tokens
            else:
                debug_info["chat_history"] += tokens

        total_tokens = sum([
            debug_info["system_prompt"],
            debug_info["chat_history"],
            debug_info["user_question"],
            *debug_info["retrieved_chunks"]
        ])

        # Print debug information in a clear format
        self.logger.info("\n" + "="*50 + "\nRAG DEBUG INFORMATION\n" + "="*50)
        self.logger.info(f"\n1. TOKEN COUNTS:")
        self.logger.info(f"   • System Prompt: {debug_info['system_prompt']} tokens")
        self.logger.info(f"   • User Question: {debug_info['user_question']} tokens")
        self.logger.info(f"   • Chat History: {debug_info['chat_history']} tokens")
        self.logger.info("\n   Retrieved Chunks:")
        for i, tokens in enumerate(debug_info["retrieved_chunks"], 1):
            self.logger.info(f"   • Chunk {i}: {tokens} tokens")
        
        self.logger.info(f"\n2. TOTAL INPUT TOKENS: {total_tokens}")
        self.logger.info(f"3. MODEL CONTEXT LIMIT: {model_limit}")
        self.logger.info(f"4. MAX COMPLETION TOKENS: {max_tokens}")
        remaining_tokens = model_limit - total_tokens - max_tokens
        
        if remaining_tokens < 0:
            self.logger.warning(f"\n⚠️ EXCEEDING MODEL LIMIT by {abs(remaining_tokens)} tokens!")
        elif remaining_tokens < 500:
            self.logger.warning(f"\n⚠️ CLOSE TO MODEL LIMIT! Only {remaining_tokens} tokens remaining")
        
        self.logger.info("="*50 + "\n")
        # return both total tokens and detected model limit so callers can act accordingly
        return {"total_tokens": total_tokens, "model_limit": model_limit}

    def set_generation_model(self,model_id:str):
        self.generate_model_id=model_id
    
    def set_embedding_model(self,model_id:str,embedding_size:int):
        self.embedding_model_id =model_id
        self.embedding_size = embedding_size


    def process_text(self,text:str):
        return text[:self.default_input_max_characters].strip()
        

    def generate_text(self,prompt:str,max_output_tokens:int=1000,chat_history:list=[],temperature:float=None):
         
        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return None
        
        if not self.generate_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return None
            
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_out_put_max_characters

        # Prepare messages: combine chat_history + current prompt
        messages = []
        if isinstance(chat_history, list):
            for item in chat_history:
                if isinstance(item, dict) and item.get("role") and item.get("content"):
                    # Process chat history items to avoid issues
                    content = item.get("content", "")
                    if content:
                        content = self.process_text(content)
                    messages.append({"role": item["role"], "content": content})

        # Don't truncate the main prompt - send it as-is for RAG scenarios
        # The prompt may contain retrieved documents and should be sent completely
        messages.append({"role": "user", "content": prompt})
        
        self.logger.info(f"Prompt length: {len(prompt)} characters (sent without truncation)")

        try:
            # GPT-5 uses max_completion_tokens instead of max_tokens
            is_gpt5 = "gpt-5" in self.generate_model_id.lower() if self.generate_model_id else False
            api_params = {
                "model": self.generate_model_id,
                "messages": messages,
                "stream": True,  # Enable streaming for faster first-token latency
            }
            # Debug prompt structure and token usage before sending request
            if self.debug_mode:
                try:
                    dbg = self.debug_prompt(messages, max_output_tokens)
                    if isinstance(dbg, dict):
                        total_tokens = dbg.get("total_tokens", 0)
                        model_limit = dbg.get("model_limit", 4096)
                        remaining = model_limit - total_tokens - max_output_tokens
                        if remaining < 0:
                            # If we're over the model limit, clear chat history (preserve system + current user prompt)
                            self.logger.warning("Total tokens exceed model context. Clearing chat history to preserve current question.")
                            # keep only system messages (if any) and the current user prompt
                            system_msgs = [m for m in messages if m.get("role") == "system"]
                            messages = []
                            messages.extend(system_msgs)
                            messages.append({"role": "user", "content": prompt})
                            # re-run debug to log new token counts
                            dbg2 = self.debug_prompt(messages, max_output_tokens)
                            if isinstance(dbg2, dict):
                                total_tokens = dbg2.get("total_tokens", 0)
                                model_limit = dbg2.get("model_limit", 4096)
                                remaining = model_limit - total_tokens - max_output_tokens
                                if remaining < 0:
                                    self.logger.warning("Even after clearing history, prompt still exceeds model limit. Will attempt to shorten context.")
                                    return self.retry_with_shorter_context(prompt, max_output_tokens, chat_history, temperature)
                        elif remaining < 500:
                            self.logger.warning("Total tokens near model context limit, may need to reduce context")
                    else:
                        # fallback: dbg may be 0 or int
                        try:
                            total_tokens = int(dbg)
                        except Exception:
                            total_tokens = 0
                except Exception as e:
                    self.logger.warning(f"Debug prompt failed: {e}")

            # GPT-5 doesn't accept temperature=None, only default (1) is supported
            if is_gpt5:
                api_params["max_completion_tokens"] = max_output_tokens
                # Don't include temperature for GPT-5 if None (uses default 1)
                if temperature is not None:
                    api_params["temperature"] = temperature
            else:
                api_params["max_tokens"] = max_output_tokens
                if temperature is not None:
                    api_params["temperature"] = temperature
            
            self.logger.info(f"Calling OpenAI API with model: {self.generate_model_id}, streaming=True")
            
            # Streaming response - collect all chunks
            stream = self.client.chat.completions.create(**api_params)
            
            if not stream:
                self.logger.error("OpenAI returned None stream")
                return "عذراً، حدث خطأ في معالجة السؤال. الرجاء المحاولة مرة أخرى."
            
            # Collect streamed chunks
            full_response = ""
            finish_reason = None
            try:
                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        choice = chunk.choices[0]
                        if hasattr(choice, 'delta') and choice.delta.content:
                            full_response += choice.delta.content
                        finish_reason = getattr(choice, 'finish_reason', None)
            except Exception as e:
                self.logger.error(f"Error during streaming: {e}", exc_info=True)
                return None
            
            if finish_reason == 'length':
                self.logger.warning("Response truncated due to length limit")
                return self.retry_with_shorter_context(prompt, max_output_tokens, chat_history, temperature)
            
            if not full_response or not full_response.strip():
                self.logger.error(f"OpenAI streaming returned empty response. Finish reason: {finish_reason}")
                return "عذراً، لم أتمكن من الحصول على إجابة واضحة. الرجاء التأكد من صياغة السؤال بشكل واضح."
                
            self.logger.info(f"Successfully generated response via streaming, length: {len(full_response)}")
            return full_response

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"OpenAI generation error: {error_msg}", exc_info=True)
            if hasattr(e, 'response') and e.response:
                self.logger.error(f"Error response: {e.response}")
            if hasattr(e, 'status_code'):
                self.logger.error(f"HTTP status code: {e.status_code}")
            return None




    def retry_with_shorter_context(self, prompt: str, max_output_tokens: int, chat_history: list, temperature: float):
        """محاولة إعادة الإجابة مع تقليل حجم السياق"""
        
        # حساب الحد الأقصى للنص
        max_length = len(prompt) // 2
        
        # تقليص السياق مع الحفاظ على السؤال الأساسي
        question_start = prompt.rfind("## السؤال:")
        if question_start != -1:
            # الاحتفاظ بالسؤال كاملاً وتقليص السياق فقط
            question = prompt[question_start:]
            context = prompt[:question_start]
            shortened_context = context[:max_length]
            new_prompt = shortened_context + question
        else:
            # إذا لم نجد علامة السؤال، نقلص النص بشكل عام
            new_prompt = prompt[:max_length]
        
        self.logger.info(f"Retrying with shorter context. Original length: {len(prompt)}, New length: {len(new_prompt)}")
        return self.generate_text(new_prompt, max_output_tokens, chat_history, temperature)

    def generate_text_streaming(self, prompt: str, max_output_tokens: int = 1000, chat_history: list = [], temperature: float = None):
        """
        Streaming generator version of generate_text.
        Yields text chunks as they arrive from the API.
        """
        if not self.client:
            self.logger.error("OpenAI Client was not set")
            return
        
        if not self.generate_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return
            
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_out_put_max_characters
        
        # Prepare messages
        messages = []
        if isinstance(chat_history, list):
            for item in chat_history:
                if isinstance(item, dict) and item.get("role") and item.get("content"):
                    content = item.get("content", "")
                    if content:
                        content = self.process_text(content)
                    messages.append({"role": item["role"], "content": content})

        messages.append({"role": "user", "content": prompt})
        
        try:
            is_gpt5 = "gpt-5" in self.generate_model_id.lower() if self.generate_model_id else False
            api_params = {
                "model": self.generate_model_id,
                "messages": messages,
                "stream": True,
            }
            
            if is_gpt5:
                api_params["max_completion_tokens"] = max_output_tokens
                if temperature is not None:
                    api_params["temperature"] = temperature
            else:
                api_params["max_tokens"] = max_output_tokens
                if temperature is not None:
                    api_params["temperature"] = temperature
            
            self.logger.info(f"Starting streaming with model: {self.generate_model_id}")
            stream = self.client.chat.completions.create(**api_params)
            
            if not stream:
                self.logger.error("OpenAI returned None stream")
                return
            
            # Yield chunks as they arrive
            full_response = ""
            finish_reason = None
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]
                    if hasattr(choice, 'delta') and choice.delta.content:
                        token = choice.delta.content
                        full_response += token
                        yield token  # Yield immediately for streaming
                    finish_reason = getattr(choice, 'finish_reason', None)
            
            self.logger.debug(f"Streaming completed. Total length: {len(full_response)}, finish_reason: {finish_reason}")
            
        except Exception as e:
            self.logger.error(f"Error during streaming: {e}", exc_info=True)
            return

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

    



        