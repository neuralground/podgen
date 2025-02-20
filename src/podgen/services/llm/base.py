from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import logging
from enum import Enum

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

class LLMService(ABC):
    """Base class for LLM services."""
    
    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate and parse JSON response."""
        pass

    @abstractmethod
    async def generate_dialogue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, str]]:
        """Generate dialogue turns from prompt."""
        pass

    def provider_name(self) -> str:
        """Get the name of the LLM provider."""
        return self.__class__.__name__.replace('Service', '')
    