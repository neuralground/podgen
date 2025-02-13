"""Enhanced LLM service with support for multiple providers."""

import aiohttp
import json
import logging
import re
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import asyncio
from pathlib import Path
import os
from openai import OpenAI

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """Available LLM providers."""
    OPENAI = "openai"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"

# System prompts for different tasks
SYSTEM_PROMPTS = {
    "content_analysis": """You are an expert content analyzer. Extract key information and insights from documents.
Always format your output as valid JSON matching the requested structure.""",
    
    "conversation": """You are an expert dialogue writer creating natural, engaging conversations.
Match the specified style and speaker characteristics.
Always format dialogue as JSON with speaker and content fields.""",
    
    "general": """You are a helpful AI assistant with expertise in many topics.
Provide clear, accurate responses."""
}

class LLMResponse:
    """Wrapper for LLM responses."""
    def __init__(self, text: str, raw: Any = None):
        self.text = text
        self.raw = raw

class LLMService:
    """Base class for LLM services."""
    
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from prompt."""
        raise NotImplementedError()
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate and parse JSON response."""
        raise NotImplementedError()

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
        # Add JSON formatting instruction
        if not "Format your response as JSON" in prompt:
            prompt += "\n\nImportant: Format your entire response as valid JSON."
        
        if system_prompt:
            system_prompt += " Always format responses as valid JSON."
        
        response = await self.generate_text(prompt, system_prompt, temperature)
        return self._parse_json_response(response)

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
        self.context_window = context_window
    
    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "temperature": temperature,
                    "stream": False
                }
                
                if system_prompt:
                    data["system"] = system_prompt
                
                async with session.post(
                    f"{self.host}/api/generate",
                    json=data
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Ollama API error: {response.status}")
                    
                    result = await response.json()
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
        return self._parse_json_response(response)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Extract and parse JSON from response."""
        try:
            # Try direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON-like content
            matches = re.findall(r'\{.*\}', response, re.DOTALL)
            if matches:
                return json.loads(matches[0])
            raise ValueError("No valid JSON found in response")

class LocalLLMFactory:
    """Factory for creating local LLM services."""
    
    @staticmethod
    def create_service(
        provider: LLMProvider,
        model_name: Optional[str] = None,
        **kwargs
    ) -> LLMService:
        """Create appropriate LLM service."""
        if provider == LLMProvider.OLLAMA:
            return OllamaService(
                model_name=model_name or "mistral:latest",
                **kwargs
            )
        elif provider == LLMProvider.LLAMACPP:
            # Could add llama.cpp support here
            raise NotImplementedError("llama.cpp support not yet implemented")
        else:
            raise ValueError(f"Unsupported local LLM provider: {provider}")

# Utility functions
def create_llm_service(
    provider: LLMProvider,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> LLMService:
    """Create LLM service based on provider."""
    if provider == LLMProvider.OPENAI:
        return OpenAIService(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    else:
        return LocalLLMFactory.create_service(provider, model_name, **kwargs)
    