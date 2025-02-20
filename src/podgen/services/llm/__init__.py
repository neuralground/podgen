from typing import Optional
from .base import LLMProvider, LLMService, SYSTEM_PROMPTS
from .openai_service import OpenAIService
from .ollama_service import OllamaService
from .prompts import PromptBuilder

def create_llm_service(
    provider: LLMProvider,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> LLMService:
    """Create appropriate LLM service based on provider."""
    if provider == LLMProvider.OPENAI:
        if not api_key:
            raise ValueError("OpenAI API key required")
        return OpenAIService(api_key=api_key, model=model_name or "gpt-4")
    elif provider == LLMProvider.OLLAMA:
        return OllamaService(
            model_name=model_name or "mistral:latest",
            host=kwargs.get('host', "http://localhost:11434")
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

__all__ = [
    'LLMProvider',
    'LLMService',
    'OpenAIService',
    'OllamaService',
    'create_llm_service',
    'PromptBuilder',
    'SYSTEM_PROMPTS'
]
