"""Base classes for TTS functionality."""

from pathlib import Path
from typing import Optional, Dict, List, Any
import logging
import asyncio
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class AudioConfig:
    """Configuration for audio generation."""
    def __init__(
        self,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        channels: int = 1,
        format: str = "wav"
    ):
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.channels = channels
        self.format = format

class VoiceConfig:
    """Voice configuration for TTS."""
    def __init__(
        self,
        voice_id: str,
        language: str = "en",
        speed: float = 1.0,
        pitch: float = 1.0,
        stability: float = 0.5,
        style: Optional[str] = None,
        accent: Optional[str] = None
    ):
        self.voice_id = voice_id
        self.language = language
        self.speed = speed
        self.pitch = pitch
        self.stability = stability
        self.style = style
        self.accent = accent

class TTSEngine(ABC):
    """Base class for TTS engines."""
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        audio_config: Optional[AudioConfig] = None
    ):
        self.model_name = model_name
        self.audio_config = audio_config or AudioConfig()
        self.loaded = False
    
    @abstractmethod
    async def load_model(self) -> bool:
        """Load the TTS model."""
        pass
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech from text."""
        pass
    
    async def _convert_audio(
        self,
        input_path: Path,
        output_path: Path,
        input_format: str = "mp3",
        output_format: str = "wav"
    ) -> bool:
        """Convert audio to desired format using ffmpeg."""
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-acodec', 'pcm_s16le',
                '-ar', str(self.audio_config.sample_rate),
                '-ac', str(self.audio_config.channels),
                str(output_path)
            ]
            
            process = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True)
            )
            
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return False

class TTSService:
    """High-level TTS service managing multiple engines."""
    
    def __init__(self):
        self.engines: List[TTSEngine] = []
        self.default_engine: Optional[TTSEngine] = None
    
    def add_engine(self, engine: TTSEngine, default: bool = False) -> None:
        """Add a TTS engine to the service."""
        self.engines.append(engine)
        if default or not self.default_engine:
            self.default_engine = engine
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None,
        engine: Optional[TTSEngine] = None
    ) -> Optional[Path]:
        """
        Synthesize speech using specified or default engine.
        
        Args:
            text: Text to synthesize
            output_path: Where to save the audio file
            voice_config: Optional voice configuration
            engine: Specific engine to use, or None for default
            
        Returns:
            Path to the generated audio file or None if synthesis failed
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Select engine
            tts_engine = engine or self.default_engine
            if not tts_engine:
                if not self.engines:
                    raise ValueError("No TTS engines available")
                tts_engine = self.engines[0]
            
            # Ensure model is loaded
            if not tts_engine.loaded:
                if not await tts_engine.load_model():
                    raise RuntimeError("Failed to load TTS model")
            
            # Synthesize speech
            success = await tts_engine.synthesize(
                text=text,
                output_path=output_path,
                voice_config=voice_config
            )
            
            return output_path if success else None
            
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return None
        