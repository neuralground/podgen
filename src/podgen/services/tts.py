from pathlib import Path
from typing import Optional, Dict, List
import pyttsx3
import subprocess
import logging
import time
import shutil
import platform
from ..models.dialogue import DialogueTurn

logger = logging.getLogger(__name__)

class TTSEngine:
    """Base class for TTS engines"""
    def synthesize(self, text: str, output_path: Path) -> bool:
        raise NotImplementedError()

class Pyttsx3Engine(TTSEngine):
    """Primary TTS engine using pyttsx3"""
    def __init__(self):
        self.engine = None
        self._init_engine()
    
    def _init_engine(self):
        if self.engine:
            try:
                self.engine.stop()
            except:
                pass
        
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 175)
        self.engine.setProperty('volume', 1.0)
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        try:
            self.engine.save_to_file(text, str(output_path))
            self.engine.runAndWait()
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception as e:
            logger.warning(f"pyttsx3 synthesis failed: {e}")
            return False

class SayEngine(TTSEngine):
    """macOS 'say' command TTS engine"""
    def __init__(self):
        self.available = platform.system() == 'Darwin' and shutil.which('say') is not None
        if self.available:
            # Get available voices
            try:
                result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True)
                self.voices = [line.split()[0] for line in result.stdout.splitlines()]
                logger.info(f"Available macOS voices: {', '.join(self.voices[:5])}...")
            except Exception as e:
                logger.warning(f"Failed to get macOS voices: {e}")
                self.voices = []
    
    def synthesize(self, text: str, output_path: Path, voice: str = 'Alex') -> bool:
        if not self.available:
            return False
            
        try:
            cmd = ['say', '-o', str(output_path), '--file-format=WAVE']
            if voice in self.voices:
                cmd.extend(['-v', voice])
            cmd.append(text)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"macOS 'say' command failed: {e}")
            return False

class EspeakEngine(TTSEngine):
    """Fallback TTS engine using espeak-ng"""
    def __init__(self):
        self.available = shutil.which('espeak-ng') is not None
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        if not self.available:
            return False
            
        try:
            result = subprocess.run(
                ['espeak-ng', '-w', str(output_path), text],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"espeak-ng synthesis failed: {e}")
            return False

class TTSService:
    """TTS service with multiple fallback engines"""
    
    def __init__(self):
        """Initialize TTS service with multiple engines."""
        # Initialize engines in priority order
        self.engines: List[TTSEngine] = []
        
        # On macOS, prioritize the native 'say' command
        if platform.system() == 'Darwin':
            self.engines.append(SayEngine())
        
        # Add other engines
        self.engines.extend([
            Pyttsx3Engine(),
            EspeakEngine()
        ])
        
        # Log available engines
        available_engines = [
            engine.__class__.__name__ 
            for engine in self.engines 
            if hasattr(engine, 'available') and engine.available
        ]
        logger.info(f"Available TTS engines: {', '.join(available_engines)}")

    def synthesize_turn(
        self,
        turn: DialogueTurn,
        output_path: Path,
        speaker_id: Optional[str] = None
    ) -> Path:
        """
        Synthesize speech using available engines.
        
        Args:
            turn: The dialogue turn to synthesize
            output_path: Where to save the audio file
            speaker_id: Optional specific speaker ID
            
        Returns:
            Path to the generated audio file
            
        Raises:
            RuntimeError: If all TTS engines fail
        """
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert wav output path to aiff for macOS if needed
        if platform.system() == 'Darwin' and output_path.suffix == '.wav':
            temp_path = output_path.with_suffix('.aiff')
        else:
            temp_path = output_path
        
        # Try each engine in order until one succeeds
        for engine in self.engines:
            try:
                if engine.synthesize(turn.content, temp_path):
                    logger.info(f"Successfully synthesized using {engine.__class__.__name__}")
                    
                    # Convert aiff to wav if needed
                    if temp_path.suffix == '.aiff':
                        try:
                            subprocess.run([
                                'ffmpeg', '-y',
                                '-i', str(temp_path),
                                '-acodec', 'pcm_s16le',
                                str(output_path)
                            ], check=True)
                            temp_path.unlink()  # Remove temporary aiff file
                        except Exception as e:
                            logger.error(f"Failed to convert aiff to wav: {e}")
                            # If conversion fails, just return the aiff file
                            return temp_path
                    
                    return output_path
            except Exception as e:
                logger.warning(f"Engine {engine.__class__.__name__} failed: {e}")
        
        raise RuntimeError("All TTS engines failed to synthesize speech")

