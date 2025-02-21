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
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.model_name = model_name
        self.host = host
        self.api_base = f"{host}/api"
        self.context_window = context_window
        self.session_manager = SessionManager()
        self.max_retries = max_retries
        self.retry_delay = retry_delay
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
            
            # Check content length (40-60 words recommended)
            words = len(turn['content'].split())
            target_words_per_turn = 50  # Based on typical podcast requirements
            if words < target_words_per_turn * 0.8:  # Allow 20% below target
                return False, f"Turn {i} content too short ({words} words)"
        
        return True, ""
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text response."""
        # Try to find JSON-like content
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            start_idx = text.find('[')
            end_idx = text.rfind(']')
        
        if start_idx != -1 and end_idx != -1:
            potential_json = text[start_idx:end_idx + 1]
            try:
                # Validate it's actually JSON
                json.loads(potential_json)
                return potential_json
            except:
                pass
        
        return text  # Return original if no JSON found

    async def _call_ollama_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Make a request to the Ollama API with retry logic."""
        if not self._model_checked:
            if not await self.check_model_availability():
                raise RuntimeError("Model not available")

        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            try:
                session = await self.session_manager.get_session()
                
                # Combine prompts differently - separate with explicit roles
                formatted_prompt = prompt
                if system_prompt:
                    formatted_prompt = f"System: {system_prompt}\n\nHuman: {prompt}\nAssistant:"
                
                data = {
                    "model": self.model_name,
                    "prompt": formatted_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": min(4096, self.context_window),
                        "stop": ["\nHuman:", "\nUser:", "\nSystem:"]
                    }
                }
                
                logger.debug(f"Sending request to Ollama: {data}")
                
                async with session.post(
                    f"{self.api_base}/generate",
                    json=data,
                    timeout=60  # Increased timeout for longer generations
                ) as response:
                    if response.status != 200:
                        error_data = await response.text()
                        raise RuntimeError(f"Ollama API error: {response.status} - {error_data}")
                    
                    result = await response.json()
                    logger.debug(f"Received response from Ollama: {result}")
                    
                    if 'error' in result:
                        raise RuntimeError(f"Ollama API error: {result['error']}")
                    
                    response_text = result.get("response", "").strip()
                    if not response_text:
                        raise RuntimeError("Empty response from Ollama")
                    
                    return response_text
                    
            except Exception as e:
                last_error = e
                retries += 1
                logger.warning(f"Attempt {retries} failed: {str(e)}")
                if retries < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** (retries - 1)))
                continue
        
        raise RuntimeError(f"Failed after {self.max_retries} retries. Last error: {last_error}")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text response."""
        try:
            return await self._call_ollama_with_retry(prompt, system_prompt, temperature)
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
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
                prompt += "\n\nIMPORTANT: Your response must be valid JSON data only. Do not include any other text."
            
            if system_prompt:
                system_prompt += " Generate only valid JSON data."
            
            response = await self._call_ollama_with_retry(prompt, system_prompt, temperature)
            
            # Clean response to extract JSON
            cleaned_response = self._extract_json(response)
            if not cleaned_response:
                raise ValueError("No JSON found in response")
            
            try:
                data = json.loads(cleaned_response)
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}\nResponse: {cleaned_response}")
                raise ValueError("Invalid JSON in response")
                
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
            # Ensure proper formatting instructions
            if not '"dialogue"' in prompt:
                prompt += '\n\nYour response must be valid JSON with a "dialogue" array.'
            
            if system_prompt:
                system_prompt = "You are a dialogue generation AI. Generate natural conversations in JSON format."
            
            response = await self._call_ollama_with_retry(prompt, system_prompt, temperature)
            
            # Try parsing as JSON first
            try:
                cleaned_response = self._extract_json(response)
                data = json.loads(cleaned_response)
                if isinstance(data, dict) and 'dialogue' in data:
                    dialogue = data['dialogue']
                    valid, error = self._validate_dialogue_format(dialogue)
                    if valid:
                        return dialogue
                    else:
                        logger.warning(f"Invalid dialogue format: {error}")
            except Exception as e:
                logger.warning(f"Failed to parse JSON response: {e}")
            
            # Fallback to text extraction
            dialogue = extract_dialogue_from_text(response)
            valid, error = self._validate_dialogue_format(dialogue)
            if valid:
                return dialogue
            else:
                logger.warning(f"Invalid extracted dialogue format: {error}")
            
            return []
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return []
        