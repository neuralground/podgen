from pathlib import Path
from typing import Optional, Dict
import pyttsx3
import logging
from ..models.dialogue import DialogueTurn

logger = logging.getLogger(__name__)

class TTSService:
    """Handles text-to-speech conversion using system speech engines via pyttsx3."""
    
    def __init__(self):
        """Initialize TTS service."""
        try:
            self.engine = pyttsx3.init()
            
            # Get available voices
            self.voices = {voice.name: voice for voice in self.engine.getProperty('voices')}
            
            # Configure default settings
            self.engine.setProperty('rate', 175)     # Speed of speech
            self.engine.setProperty('volume', 1.0)   # Volume level
            
            # Default to first available voice
            if self.voices:
                self.engine.setProperty('voice', list(self.voices.values())[0].id)
            
            logger.info(f"Initialized TTS service with {len(self.voices)} available voices")
            
            # Log available voices
            for voice in self.voices.values():
                logger.info(f"Available voice: {voice.name} ({voice.id})")
            
        except Exception as e:
            logger.error(f"Failed to initialize TTS service: {e}")
            raise

    def get_available_voices(self) -> Dict[str, str]:
        """Get a dictionary of available voice names and their IDs."""
        return {voice.name: voice.id for voice in self.voices.values()}

    def synthesize_turn(
        self,
        turn: DialogueTurn,
        output_path: Path,
        speaker_id: Optional[str] = None
    ) -> Path:
        """
        Synthesize speech for a single dialogue turn.
        
        Args:
            turn: The dialogue turn to synthesize
            output_path: Where to save the audio file
            speaker_id: Optional specific speaker ID to use
            
        Returns:
            Path to the generated audio file
        """
        try:
            # Set voice if specified
            if speaker_id and speaker_id in self.voices:
                self.engine.setProperty('voice', self.voices[speaker_id].id)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate speech
            self.engine.save_to_file(turn.content, str(output_path))
            self.engine.runAndWait()
            
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to synthesize speech: {e}")
            raise
            
    def list_voices(self) -> None:
        """Print available voices to the logger."""
        logger.info("Available voices:")
        for voice in self.voices.values():
            logger.info(f"- Name: {voice.name}")
            logger.info(f"  ID: {voice.id}")
            logger.info(f"  Languages: {voice.languages}")
            logger.info(f"  Gender: {voice.gender}")
            logger.info("---")

