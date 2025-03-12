"""Text-to-Speech service package."""

from enum import Enum
from typing import Optional, Dict, Any

# Import base classes
from .base import TTSEngine, TTSService

# Import cloud providers
from .cloud import (
    ElevenLabsEngine,
    OpenAITTSEngine
)

# Import local providers
from .local import (
    CoquiTTSEngine,
    BarkEngine,
    OllamaTTSEngine
)

class TTSProvider(str, Enum):
    """Available TTS providers."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    COQUI = "coqui"
    BARK = "bark"
    OLLAMA = "ollama"
    SYSTEM = "system"

# Mapping of provider to engine class
PROVIDER_MAP = {
    TTSProvider.ELEVENLABS: ElevenLabsEngine,
    TTSProvider.OPENAI: OpenAITTSEngine,
    TTSProvider.COQUI: CoquiTTSEngine,
    TTSProvider.BARK: BarkEngine,
    TTSProvider.OLLAMA: OllamaTTSEngine
}

# Default model names for local providers
DEFAULT_MODELS = {
    TTSProvider.COQUI: "tts_models/en/vctk/vits",
    TTSProvider.BARK: None,  # Uses built-in models
    TTSProvider.OLLAMA: "mistral-tts"
}

def create_engine(
    provider: TTSProvider,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> Optional[TTSEngine]:
    """Create appropriate TTS engine based on provider."""
    if provider not in PROVIDER_MAP:
        return None

    engine_class = PROVIDER_MAP[provider]
    if not model_name and provider in DEFAULT_MODELS:
        model_name = DEFAULT_MODELS[provider]

    # Only pass api_key to cloud providers
    if provider in [TTSProvider.ELEVENLABS, TTSProvider.OPENAI]:
        return engine_class(model_name=model_name, api_key=api_key, **kwargs)
    else:
        return engine_class(model_name=model_name, **kwargs)

__all__ = [
    # Base classes
    "TTSEngine",
    "TTSService",
    
    # Providers
    "TTSProvider",
    "ElevenLabsEngine",
    "OpenAITTSEngine",
    "CoquiTTSEngine", 
    "BarkEngine",
    "OllamaTTSEngine",
    
    # Factory function
    "create_engine",
    
    # Constants
    "DEFAULT_MODELS",
    "PROVIDER_MAP"
]
