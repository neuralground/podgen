"""Core services for podcast generation."""

from enum import Enum
from typing import Optional

# Import core services
from .audio import AudioProcessor
from .conversation import ConversationGenerator
from .content_analyzer import ContentAnalyzer
from .podcast_generator import PodcastGenerator

# Import LLM service and types
from .llm import (
    LLMService,
    LLMProvider,
    OllamaService,
    create_llm_service,
    SYSTEM_PROMPTS
)

# Import TTS service and types
from .tts import (
    TTSService,
    TTSProvider,
    TTSEngine,
    # Cloud providers
    ElevenLabsEngine,
    OpenAITTSEngine,
    # Local providers
    CoquiTTSEngine,
    BarkEngine,
    OllamaTTSEngine
)

class ModelType(str, Enum):
    """Model deployment type."""
    LOCAL = "local"
    CLOUD = "cloud"
    SYSTEM = "system"

def create_tts_service(
    provider: TTSProvider,
    model_name: Optional[str] = None,
    **kwargs
) -> TTSService:
    """Create TTS service based on provider."""
    return TTSService(provider=provider, model_name=model_name, **kwargs)

__all__ = [
    # Core services
    "AudioProcessor",
    "ConversationGenerator",
    "ContentAnalyzer",
    "PodcastGenerator",
    
    # LLM types and services
    "LLMService",
    "LLMProvider",
    "OllamaService",
    "create_llm_service",
    "SYSTEM_PROMPTS",
    
    # TTS types and services
    "TTSService",
    "TTSProvider",
    "TTSEngine",
    "ElevenLabsEngine",
    "OpenAITTSEngine",
    "CoquiTTSEngine",
    "BarkEngine",
    "OllamaTTSEngine",
    
    # Enums and factories
    "ModelType",
    "create_tts_service"
]
