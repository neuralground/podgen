"""Model configuration management for podgen."""

from enum import Enum
from typing import Optional
from pathlib import Path
import logging

from ...config import settings
from ...services.llm import LLMProvider
from ...services.tts import TTSProvider

logger = logging.getLogger(__name__)

class LLMType(str, Enum):
    """LLM provider types for CLI use."""
    openai = "openai"
    ollama = "ollama"
    llamacpp = "llamacpp"

class ModelConfig:
    """Configuration for model selection."""
    
    def __init__(
        self,
        llm_type: Optional[LLMType] = None,
        llm_model: Optional[str] = None,
        tts_type: Optional[TTSProvider] = None,
        tts_model: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        """Initialize with optional overrides for defaults."""
        # Use settings from config as defaults
        self.llm_type = llm_type or LLMType(settings.llm_provider.value)
        self.llm_model = llm_model or settings.llm_model
        self.tts_type = tts_type or settings.tts_provider
        self.tts_model = tts_model or settings.tts_model
        self.output_dir = output_dir or settings.paths.get_path("output")
        
        # Log configuration
        logger.info(f"Model configuration: LLM={self.llm_type}/{self.llm_model}, "
                   f"TTS={self.tts_type}/{self.tts_model}")

    @property
    def llm_provider(self) -> LLMProvider:
        """Get LLM provider enum from type."""
        return LLMProvider(self.llm_type.value)

    @property
    def tts_provider(self) -> TTSProvider:
        """Get TTS provider enum."""
        return self.tts_type
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "llm_type": self.llm_type.value,
            "llm_model": self.llm_model,
            "tts_type": self.tts_type.value,
            "tts_model": self.tts_model,
            "output_dir": str(self.output_dir)
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ModelConfig':
        """Create configuration from dictionary."""
        return cls(
            llm_type=LLMType(data.get("llm_type", settings.llm_provider.value)),
            llm_model=data.get("llm_model", settings.llm_model),
            tts_type=TTSProvider(data.get("tts_type", settings.tts_provider.value)),
            tts_model=data.get("tts_model", settings.tts_model),
            output_dir=Path(data.get("output_dir", str(settings.paths.get_path("output"))))
        )
    
    def save_to_file(self, name: str = "default") -> Optional[Path]:
        """Save configuration to file."""
        try:
            config_path = settings.paths.get_config_path(f"model_config_{name}")
            settings.paths.save_json("config", f"model_config_{name}.json", self.to_dict())
            logger.info(f"Saved model configuration to {config_path}")
            return config_path
        except Exception as e:
            logger.error(f"Error saving model configuration: {e}")
            return None
    
    @classmethod
    def load_from_file(cls, name: str = "default") -> Optional['ModelConfig']:
        """Load configuration from file."""
        try:
            config_data = settings.paths.load_json("config", f"model_config_{name}.json")
            if not config_data:
                logger.warning(f"No saved configuration found for '{name}'")
                return None
            
            logger.info(f"Loaded model configuration '{name}'")
            return cls.from_dict(config_data)
        except Exception as e:
            logger.error(f"Error loading model configuration: {e}")
            return None
        