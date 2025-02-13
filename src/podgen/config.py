"""Configuration management for podgen."""

from pathlib import Path
from typing import Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from enum import Enum

# Try to import torch, but default to CPU if not available
try:
    import torch
    DEFAULT_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    DEFAULT_DEVICE = "cpu"

class LLMProvider(str, Enum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"

class TTSProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    COQUI = "coqui"
    BARK = "bark"
    OLLAMA = "ollama"
    SYSTEM = "system"

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Settings
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    elevenlabs_api_key: str = Field("", env="ELEVENLABS_API_KEY")
    
    # Model Settings
    llm_provider: LLMProvider = Field(LLMProvider.OPENAI, env="LLM_PROVIDER")
    llm_model: str = Field("gpt-4", env="LLM_MODEL")
    llm_temperature: float = Field(0.7, env="LLM_TEMPERATURE")
    max_tokens: int = Field(2000, env="MAX_TOKENS")
    
    # Ollama Settings
    ollama_host: str = Field("http://localhost:11434", env="OLLAMA_HOST")
    
    # TTS Settings
    tts_provider: TTSProvider = Field(TTSProvider.SYSTEM, env="TTS_PROVIDER")
    tts_model: Optional[str] = Field(None, env="TTS_MODEL")
    
    # Audio Settings
    sample_rate: int = Field(44100, env="SAMPLE_RATE")
    crossfade_duration: float = Field(0.5, env="CROSSFADE_DURATION")
    output_format: str = Field("wav", env="OUTPUT_FORMAT")
    
    # Paths
    output_dir: Path = Field(Path("output"), env="OUTPUT_DIR")
    cache_dir: Path = Field(Path(".cache"), env="CACHE_DIR")
    data_dir: Path = Field(Path("data"), env="DATA_DIR")
    models_dir: Path = Field(Path("models"), env="MODELS_DIR")
    
    # Device Settings
    device: str = Field(DEFAULT_DEVICE, env="DEVICE")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: Optional[Path] = Field(None, env="LOG_FILE")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Allow extra fields in .env file
    )
    
    @field_validator("output_dir", "cache_dir", "data_dir", "models_dir")
    def create_directory(cls, v: Path) -> Path:
        """Ensure directories exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v

# Create global settings instance
settings = Settings()

def init_directories() -> None:
    """Initialize required directories."""
    settings.output_dir.mkdir(exist_ok=True)
    settings.cache_dir.mkdir(exist_ok=True)
    settings.data_dir.mkdir(exist_ok=True)
    settings.models_dir.mkdir(exist_ok=True)

def get_llm_service():
    """Create LLM service based on configuration."""
    from .services import create_llm_service
    return create_llm_service(
        provider=settings.llm_provider,
        model_name=settings.llm_model,
        api_key=settings.openai_api_key,
        host=settings.ollama_host
    )

def get_tts_service():
    """Create TTS service based on configuration."""
    from .services import create_tts_service
    return create_tts_service(
        provider=settings.tts_provider,
        model_name=settings.tts_model,
        api_key=settings.elevenlabs_api_key,
        device=settings.device
    )

