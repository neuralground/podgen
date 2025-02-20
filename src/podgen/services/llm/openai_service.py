import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from .base import LLMService
from .response_parser import parse_json_response

logger = logging.getLogger(__name__)

class OpenAIService(LLMService):
    """LLM service using OpenAI API."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

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
        
        response = await self.generate_text(prompt, system_prompt, temperature)
        return parse_json_response(response)

    async def generate_dialogue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, str]]:
        """Generate dialogue turns from prompt."""
        if not '"dialogue"' in prompt:
            prompt += '\n\nFormat your response as JSON with "dialogue" array.'
        
        if system_prompt:
            system_prompt += " Format the dialogue as a JSON array."
            
        try:
            response = await self.generate_text(prompt, system_prompt, temperature)
            data = parse_json_response(response)
            
            if isinstance(data, dict) and 'dialogue' in data:
                return data['dialogue']
            
            logger.warning("Response didn't contain dialogue array")
            return []
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return []