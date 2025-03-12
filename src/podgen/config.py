"""Configuration management for podgen with enhanced path management."""

import os
from pathlib import Path
from typing import Optional, Union, Dict, Any, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, SecretStr, validator
from enum import Enum
import logging
import keyring
import getpass
import json

logger = logging.getLogger(__name__)

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

# Get default podgen directory - prioritize environment variable or fallback to home directory
DEFAULT_PODGEN_DIR = os.getenv('PODGEN_DIR', str(Path.home() / '.podgen'))

class PathManager:
    """Manages all file paths used by the application."""
    
    def __init__(self, base_dir: Union[str, Path]):
        """Initialize with the base directory."""
        self.base_dir = Path(base_dir)
        
        # Create the base directory if it doesn't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Define standard subdirectories
        self.subdirs = {
            "output": self.base_dir / "output",  # For generated podcasts
            "cache": self.base_dir / "cache",    # For cached data
            "data": self.base_dir / "data",      # For database files
            "models": self.base_dir / "models",  # For downloaded models
            "logs": self.base_dir / "logs",      # For log files
            "temp": self.base_dir / "temp",      # For temporary files
            "config": self.base_dir / "config",  # For configuration files
        }
        
        # Create all subdirectories
        for subdir in self.subdirs.values():
            subdir.mkdir(parents=True, exist_ok=True)
            
        # Log directory initialization
        logger.debug(f"Initialized path manager with base directory: {self.base_dir}")
        for name, path in self.subdirs.items():
            logger.debug(f"  {name}: {path}")
    
    def get_path(self, category: str) -> Path:
        """Get the path for a specific category."""
        if category in self.subdirs:
            return self.subdirs[category]
        else:
            # If an unknown category is requested, create it and return
            new_path = self.base_dir / category
            new_path.mkdir(parents=True, exist_ok=True)
            self.subdirs[category] = new_path
            return new_path
    
    def get_file_path(self, category: str, filename: str) -> Path:
        """Get a path to a specific file within a category."""
        return self.get_path(category) / filename
    
    def ensure_exists(self, path: Path) -> Path:
        """Ensure a directory exists and return it."""
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path
    
    def list_files(self, category: str, pattern: str = "*") -> List[Path]:
        """List all files in a category matching a pattern."""
        return list(self.get_path(category).glob(pattern))
    
    def get_db_path(self, db_name: str) -> Path:
        """Get the path to a database file."""
        return self.get_file_path("data", f"{db_name}.db")
    
    def get_log_path(self, log_name: str) -> Path:
        """Get the path to a log file."""
        return self.get_file_path("logs", f"{log_name}.log")
    
    def get_config_path(self, config_name: str) -> Path:
        """Get the path to a configuration file."""
        return self.get_file_path("config", f"{config_name}.json")
    
    def get_output_path(self, filename: str) -> Path:
        """Get the path to an output file."""
        return self.get_file_path("output", filename)
    
    def get_unique_output_path(self, prefix: str, suffix: str = ".wav") -> Path:
        """Generate a unique output path with timestamp."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.get_output_path(f"{prefix}_{timestamp}{suffix}")
    
    def save_json(self, category: str, filename: str, data: dict) -> Path:
        """Save JSON data to a file."""
        path = self.get_file_path(category, filename)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path
    
    def load_json(self, category: str, filename: str, default: Optional[dict] = None) -> dict:
        """Load JSON data from a file."""
        path = self.get_file_path(category, filename)
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
        return default or {}
    
    def clear_category(self, category: str, confirm: bool = True) -> bool:
        """Clear all files in a category."""
        if confirm:
            response = input(f"Are you sure you want to clear all files in {category}? (y/n): ")
            if response.lower() not in ['y', 'yes']:
                return False
        
        path = self.get_path(category)
        for item in path.glob("*"):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
        return True

class SecureKeyManager:
    """Manages secure storage and retrieval of API keys."""
    
    APP_NAME = "podgen"
    
    @staticmethod
    def get_key(service_name: str) -> Optional[str]:
        """Retrieve an API key from secure storage."""
        try:
            key = keyring.get_password(SecureKeyManager.APP_NAME, service_name)
            return key
        except Exception as e:
            logger.error(f"Failed to retrieve key for {service_name}: {e}")
            return None
    
    @staticmethod
    def set_key(service_name: str, key: str) -> bool:
        """Store an API key in secure storage."""
        try:
            keyring.set_password(SecureKeyManager.APP_NAME, service_name, key)
            return True
        except Exception as e:
            logger.error(f"Failed to store key for {service_name}: {e}")
            return False
    
    @staticmethod
    def delete_key(service_name: str) -> bool:
        """Delete an API key from secure storage."""
        try:
            keyring.delete_password(SecureKeyManager.APP_NAME, service_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key for {service_name}: {e}")
            return False
    
    @staticmethod
    def prompt_for_key(service_name: str, force_input: bool = False) -> Optional[str]:
        """Prompt user for API key and store it securely."""
        existing_key = None if force_input else SecureKeyManager.get_key(service_name)
        
        if existing_key and not force_input:
            return existing_key
        
        try:
            print(f"Please enter your {service_name} API key (input will be hidden):")
            key = getpass.getpass()
            
            if key:
                SecureKeyManager.set_key(service_name, key)
                return key
            return None
        except Exception as e:
            logger.error(f"Failed to prompt for {service_name} key: {e}")
            return None

class Settings(BaseSettings):
    """Application settings loaded from environment variables with secure API key handling."""
    
    # Base directory
    podgen_dir: Path = Field(DEFAULT_PODGEN_DIR, env="PODGEN_DIR")
    
    # Paths derived from base directory - these will be set in __init__
    output_dir: Optional[Path] = Field(None, env="OUTPUT_DIR")
    cache_dir: Optional[Path] = Field(None, env="CACHE_DIR")
    data_dir: Optional[Path] = Field(None, env="DATA_DIR")
    models_dir: Optional[Path] = Field(None, env="MODELS_DIR")
    logs_dir: Optional[Path] = Field(None, env="LOGS_DIR")
    
    paths: Optional[PathManager] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    def __init__(self, **kwargs):
        # Clean environment variables that might have comments
        self._clean_env_vars()
        
        super().__init__(**kwargs)
        
        # Initialize path manager
        self.paths = PathManager(self.podgen_dir)
        
        # Set up derived paths using the path manager
        self.output_dir = self.paths.get_path("output")
        self.cache_dir = self.paths.get_path("cache")
        self.data_dir = self.paths.get_path("data")
        self.models_dir = self.paths.get_path("models")
        self.logs_dir = self.paths.get_path("logs")
        
        # Configure logging to file
        if self.log_level and not self.log_file:
            # Default log file if not specified
            self.log_file = self.paths.get_log_path("podgen")
    
    def _clean_env_vars(self):
        """Clean environment variables by removing comments."""
        for var_name in ["LLM_PROVIDER", "TTS_PROVIDER"]:
            if var_name in os.environ:
                # Remove comments (anything after #)
                value = os.environ[var_name].split('#')[0].strip()
                os.environ[var_name] = value
                logger.debug(f"Cleaned environment variable {var_name}: '{value}'")
    
    # API Settings - using key references instead of actual keys
    openai_api_key_ref: Optional[str] = Field("", env="OPENAI_API_KEY_REF")
    elevenlabs_api_key_ref: Optional[str] = Field("", env="ELEVENLABS_API_KEY_REF")
    
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
    
    # Device Settings
    device: str = Field(DEFAULT_DEVICE, env="DEVICE")
    
    # Logging
    log_level: str = Field("DEBUG", env="LOG_LEVEL")
    log_file: Optional[Path] = Field(None, env="LOG_FILE")
    
    # Helper methods for secure API keys
    def get_openai_api_key(self, prompt_if_missing: bool = False) -> Optional[str]:
        """Get OpenAI API key from secure storage."""
        # First check environment variable directly (for backward compatibility and CI/CD usage)
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            return env_key
            
        if self.openai_api_key_ref:
            key = SecureKeyManager.get_key(self.openai_api_key_ref)
            if key:
                return key
        
        if prompt_if_missing:
            # Default key reference if not specified
            service_name = self.openai_api_key_ref or "openai-api"
            return SecureKeyManager.prompt_for_key(service_name)
        
        return None
    
    def get_elevenlabs_api_key(self, prompt_if_missing: bool = False) -> Optional[str]:
        """Get ElevenLabs API key from secure storage."""
        # First check environment variable directly (for backward compatibility and CI/CD usage)
        env_key = os.environ.get("ELEVENLABS_API_KEY")
        if env_key:
            return env_key
            
        if self.elevenlabs_api_key_ref:
            key = SecureKeyManager.get_key(self.elevenlabs_api_key_ref)
            if key:
                return key
        
        if prompt_if_missing:
            # Default key reference if not specified
            service_name = self.elevenlabs_api_key_ref or "elevenlabs-api"
            return SecureKeyManager.prompt_for_key(service_name)
        
        return None
    
    def setup_logging(self):
        """Configure logging based on settings."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create file handler - all logs go to file
        if self.log_file:
            # Ensure parent directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(level)
            file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_format)
            root_logger.addHandler(file_handler)
            
            # Only log warnings and errors to console
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_format = logging.Formatter('%(levelname)s: %(message)s')
            console_handler.setFormatter(console_format)
            root_logger.addHandler(console_handler)
            
            logger.info(f"Logging to file: {self.log_file}")
        else:
            # If no log file is specified, create minimal console handler for warnings/errors
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_format = logging.Formatter('%(levelname)s: %(message)s')
            console_handler.setFormatter(console_format)
            root_logger.addHandler(console_handler)

# Create global settings instance
settings = Settings()

# Initialize logging after settings are created
settings.setup_logging()

def initialize_api_keys(interactive: bool = True) -> Dict[str, bool]:
    """Initialize API keys, optionally prompting the user.
    
    Returns a dictionary indicating which keys are available.
    """
    result = {}
    
    # Check for OpenAI API key
    openai_key = settings.get_openai_api_key(prompt_if_missing=interactive)
    result["openai"] = bool(openai_key)
    
    # Check for ElevenLabs API key
    elevenlabs_key = settings.get_elevenlabs_api_key(prompt_if_missing=interactive)
    result["elevenlabs"] = bool(elevenlabs_key)
    
    return result

def get_llm_service():
    """Create LLM service based on configuration."""
    from ..services import create_llm_service
    
    # Get API key if needed
    api_key = None
    if settings.llm_provider == LLMProvider.OPENAI:
        api_key = settings.get_openai_api_key(prompt_if_missing=True)
        if not api_key:
            raise ValueError("OpenAI API key is required but not available")
    
    return create_llm_service(
        provider=settings.llm_provider,
        model_name=settings.llm_model,
        api_key=api_key,
        host=settings.ollama_host
    )

def get_tts_service():
    """Create TTS service based on configuration."""
    from ..services import create_tts_service
    
    # Get API key if needed
    api_key = None
    if settings.tts_provider == TTSProvider.ELEVENLABS:
        api_key = settings.get_elevenlabs_api_key(prompt_if_missing=True)
        if not api_key:
            raise ValueError("ElevenLabs API key is required but not available")
    elif settings.tts_provider == TTSProvider.OPENAI:
        api_key = settings.get_openai_api_key(prompt_if_missing=True)
        if not api_key:
            raise ValueError("OpenAI API key is required but not available")
    
    return create_tts_service(
        provider=settings.tts_provider,
        model_name=settings.tts_model,
        api_key=api_key,
        device=settings.device
    )
