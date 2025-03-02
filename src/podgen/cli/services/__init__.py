"""CLI services package."""

from .completion import setup_completion
from .player import AudioPlayer
from .model_config import ModelConfig

__all__ = ['setup_completion', 'AudioPlayer', 'ModelConfig']
