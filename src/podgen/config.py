"""
Configuration management for podgen.
"""

from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Model Settings
    default_llm_model: str = Field("gpt-4", env="DEFAULT_LLM_MODEL")
    llm_temperature: float = Field(0.7, env="LLM_TEMPERATURE")
    max_tokens: int = Field(2000, env="MAX_TOKENS")
    
    # TTS Settings
    tts_model: str = Field("tts_models/en/vctk/vits", env="TTS_MODEL")
    device: str = Field("cuda", env="DEVICE")
    
    # Audio Settings
    sample_rate: int = Field(44100, env="SAMPLE_RATE")
    crossfade_duration: float = Field(0.5, env="CROSSFADE_DURATION")
    output_format: str = Field("wav", env="OUTPUT_FORMAT")
    
    # Paths
    output_dir: Path = Field(Path("output"), env="OUTPUT_DIR")
    cache_dir: Path = Field(Path(".cache"), env="CACHE_DIR")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: Optional[Path] = Field(None, env="LOG_FILE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Create global settings instance
settings = Settings()

def init_directories() -> None:
    """Initialize required directories."""
    settings.output_dir.mkdir(exist_ok=True)
    settings.cache_dir.mkdir(exist_ok=True)

