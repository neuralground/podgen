from pathlib import Path
from typing import Optional
import torch
from TTS.api import TTS
import logging
from ..models.dialogue import DialogueTurn

logger = logging.getLogger(__name__)

class TTSService:
    """Handles text-to-speech conversion."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize TTS service.
        
        Args:
            model_path: Optional path to custom TTS model
        """
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.tts = TTS(model_path if model_path else "tts_models/en/vctk/vits")
            logger.info(f"Initialized TTS service using device: {self.device}")
        except Exception as e:
            logger.error(f"Failed to initialize TTS service: {e}")
            raise

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
            self.tts.tts_to_file(
                text=turn.content,
                speaker=speaker_id or turn.speaker.voice_id,
                file_path=str(output_path)
            )
            return output_path
        except Exception as e:
            logger.error(f"Failed to synthesize speech: {e}")
            raise


