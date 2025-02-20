import json
import logging
import aiohttp
from typing import Dict, Any, List, Optional
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
        context_window: int = 4096
    ):
        self.model_name = model_name
        self.host = host
        self.api_base = f"{host}/api"
        self.context_window = context_window
        self.session_manager = SessionManager()
    
    async def _check_model_availability(self) -> bool:
        """Check if the model is available on the Ollama server."""
        try:
            session = await self.session_manager.get_session()
            async with session.get(f"{self.api_base}/tags") as response:
                if response.status != 200:
                    logger.error(f"Ollama server not available: {response.status}")
                    return False
                
                data = await response.json()
                models = [m.get('name') for m in data.get('models', [])]
                
                if self.model_name not in models:
                    logger.error(f"Model {self.model_name} not found. Available models: {models}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to check model availability: {e}")
            return False
    
    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Make a request to the Ollama API."""
        try:
            if not await self._check_model_availability():
                raise RuntimeError("Model not available")
            
            session = await self.session_manager.get_session()
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "temperature": temperature,
                "stream": False,
                "raw": True  # Request raw output
            }
            
            if system_prompt:
                data["system"] = system_prompt
            
            async with session.post(
                f"{self.api_base}/generate",
                json=data
            ) as response:
                if response.status != 200:
                    error_data = await response.text()
                    logger.error(f"Ollama API error: {response.status} - {error_data}")
                    raise RuntimeError(f"Ollama API error: {response.status}")
                
                result = await response.json()
                if 'error' in result:
                    raise RuntimeError(f"Ollama API error: {result['error']}")
                
                return result.get("response", "")
                
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        return await self._call_ollama(prompt, system_prompt, temperature)

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if not "Format your response as JSON" in prompt:
            prompt += "\n\nImportant: Format your entire response as valid JSON."
        
        if system_prompt:
            system_prompt += " Always format responses as valid JSON."
        
        response = await self._call_ollama(prompt, system_prompt, temperature)
        return parse_json_response(response)

    async def generate_dialogue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, str]]:
        """Generate dialogue turns from prompt."""
        try:
            if system_prompt is None:
                system_prompt = "You are a dialogue generator. Always output valid JSON with a 'dialogue' array containing speaker turns."
            else:
                system_prompt += " Always output valid JSON with a 'dialogue' array."

            response = await self._call_ollama(prompt, system_prompt, temperature)
            
            # Try parsing as JSON first
            try:
                data = parse_json_response(response)
                if isinstance(data, dict) and 'dialogue' in data:
                    return data['dialogue']
            except:
                pass
            
            # If JSON parsing fails, try extracting dialogue directly
            return extract_dialogue_from_text(response)
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return []
        