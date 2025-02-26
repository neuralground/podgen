import json
import logging
import aiohttp
from typing import Dict, Any, List, Optional, Tuple
import asyncio

from .base import LLMService
from .response_parser import parse_json_response, extract_dialogue_from_text
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

class OllamaService(LLMService):
    """LLM service using Ollama."""
    
    def __init__(
        self,
        model_name: str = "mistral:latest",
        host: str = "http://localhost:11434",
        context_window: int = 4096,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        timeout: int = 60
    ):
        self.model_name = model_name
        self.host = host
        self.api_base = f"{host}/api"
        self.context_window = context_window
        self.session_manager = SessionManager()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self._model_checked = False
    
    async def check_model_availability(self) -> bool:
        """Check if the model is available on the Ollama server."""
        try:
            session = await self.session_manager.get_session()
            async with session.get(f"{self.api_base}/tags") as response:
                if response.status != 200:
                    logger.error(f"Ollama server not available: {response.status}")
                    return False
                
                data = await response.json()
                models = [m.get('name', '').split(':')[0] for m in data.get('models', [])]
                model_base = self.model_name.split(':')[0]
                
                if model_base not in models:
                    logger.error(f"Model {self.model_name} not found. Available models: {models}")
                    return False
                
                self._model_checked = True
                return True
                
        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
            return False

    def _validate_dialogue_format(self, dialogue: List[Dict[str, str]]) -> Tuple[bool, str]:
        """Validate dialogue format and structure."""
        if not isinstance(dialogue, list):
            return False, "Dialogue must be a list"
        
        if not dialogue:
            return False, "Dialogue cannot be empty"
        
        for i, turn in enumerate(dialogue):
            if not isinstance(turn, dict):
                return False, f"Turn {i} must be a dictionary"
            
            if 'speaker' not in turn or 'content' not in turn:
                return False, f"Turn {i} must have 'speaker' and 'content' fields"
            
            if not isinstance(turn['speaker'], str) or not isinstance(turn['content'], str):
                return False, f"Turn {i} fields must be strings"
            
            if not turn['speaker'].strip() or not turn['content'].strip():
                return False, f"Turn {i} fields cannot be empty"
            
            words = len(turn['content'].split())
            if words < 40:  # Minimum words per turn
                return False, f"Turn {i} content too short ({words} words)"
        
        return True, ""

    async def _process_chunk(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Process a single chunk of the prompt."""
        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            try:
                session = await self.session_manager.get_session()
                
                # Format prompt based on model type
                if self.model_name.startswith('deepseek'):
                    formatted_prompt = prompt
                    if system_prompt:
                        formatted_prompt = f"System: {system_prompt}\n\nUser: {prompt}\nAssistant:"
                else:
                    formatted_prompt = prompt
                
                data = {
                    "model": self.model_name,
                    "prompt": formatted_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": min(2048, self.context_window),
                        "stop": ["\nUser:", "\nAssistant:", "\nSystem:"]
                    }
                }
                
                logger.debug(f"Sending request to Ollama (attempt {retries + 1})")
                logger.debug(f"Prompt length: {len(formatted_prompt)}")
                
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with session.post(
                    f"{self.api_base}/generate",
                    json=data,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Ollama API error (status {response.status}): {error_text}")
                        raise RuntimeError(f"Ollama API error: {response.status} - {error_text}")
                    
                    result = await response.json()
                    
                    if 'error' in result:
                        raise RuntimeError(f"Ollama API error: {result['error']}")
                    
                    response_text = result.get("response", "").strip()
                    if not response_text:
                        raise RuntimeError("Empty response from Ollama")
                    
                    logger.debug(f"Received response of length {len(response_text)}")
                    return response_text

            except asyncio.TimeoutError:
                logger.warning(f"Request timed out (attempt {retries + 1}/{self.max_retries})")
                last_error = "Request timed out"
                retries += 1
                if retries < self.max_retries:
                    delay = self.retry_delay * (2 ** retries)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(f"Request failed (attempt {retries + 1}): {str(e)}")
                last_error = str(e)
                retries += 1
                if retries < self.max_retries:
                    delay = self.retry_delay * (2 ** retries)
                    await asyncio.sleep(delay)
                continue

        raise RuntimeError(f"Failed after {self.max_retries} retries. Last error: {last_error}")

    async def _call_ollama_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Make a request to the Ollama API with retry logic."""
        if not self._model_checked:
            logger.info(f"Checking model availability: {self.model_name}")
            if not await self.check_model_availability():
                raise RuntimeError(f"Model {self.model_name} not available")

        # For large models, break prompt into smaller chunks
        max_chunk_size = 2000  # Maximum characters per chunk
        if len(prompt) > max_chunk_size and self.model_name.endswith(('70b', '34b')):
            chunks = [prompt[i:i + max_chunk_size] for i in range(0, len(prompt), max_chunk_size)]
            logger.info(f"Breaking prompt into {len(chunks)} chunks")
            responses = []
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                try:
                    response = await self._process_chunk(chunk, system_prompt, temperature)
                    if response:
                        responses.append(response)
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}")
                    continue
            
            return " ".join(responses)
        
        # For smaller prompts, process directly
        return await self._process_chunk(prompt, system_prompt, temperature)

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text response."""
        try:
            logger.info("Starting text generation")
            logger.debug(f"Prompt length: {len(prompt)}")
            if system_prompt:
                logger.debug(f"System prompt length: {len(system_prompt)}")
            
            response = await self._call_ollama_with_retry(prompt, system_prompt, temperature)
            if not response:
                logger.error("Empty response from Ollama")
                return ""
            
            logger.info(f"Generated response of length {len(response)}")
            return response
            
        except Exception as e:
            logger.error(f"Text generation failed: {str(e)}")
            return ""

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate and parse JSON response."""
        try:
            # Add explicit JSON formatting instructions
            if not "Format your response as JSON" in prompt:
                prompt += "\n\nIMPORTANT: Format your entire response as valid JSON. Include only the JSON data without any other text."
            
            if system_prompt:
                system_prompt += " Generate only valid JSON data."
            
            response = await self._call_ollama_with_retry(prompt, system_prompt, temperature)
            if not response:
                return {}
            
            # Parse response as JSON
            try:
                return parse_json_response(response)
            except Exception as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Response content: {response[:500]}...")  # Log first 500 chars
                return {}
                
        except Exception as e:
            logger.error(f"JSON generation failed: {e}")
            return {}

    async def generate_dialogue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, str]]:
        """Generate dialogue turns from prompt."""
        try:
            # Ensure proper dialogue formatting instructions
            if not '"dialogue"' in prompt:
                prompt += '\n\nFormat your response as a dialogue. Each turn should include a speaker and their response.'
            
            if system_prompt:
                system_prompt = "Generate a natural conversation following the format requested."
            
            # Generate response
            response = await self._call_ollama_with_retry(prompt, system_prompt, temperature)
            if not response:
                return []
            
            # Try parsing as JSON first
            try:
                data = parse_json_response(response)
                if isinstance(data, dict) and 'dialogue' in data:
                    dialogue = data['dialogue']
                    valid, error = self._validate_dialogue_format(dialogue)
                    if valid:
                        return dialogue
                    else:
                        logger.warning(f"Invalid dialogue format: {error}")
            except Exception as e:
                logger.warning(f"Failed to parse JSON dialogue: {e}")
            
            # Fallback to text extraction
            dialogue = extract_dialogue_from_text(response)
            valid, error = self._validate_dialogue_format(dialogue)
            if valid:
                return dialogue
            else:
                logger.warning(f"Invalid extracted dialogue: {error}")
            
            return []
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return []
