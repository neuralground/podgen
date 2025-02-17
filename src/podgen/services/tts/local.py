"""Local TTS engine implementations."""

import torch
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio
import tempfile
import subprocess
import numpy as np
import soundfile as sf
from concurrent.futures import ThreadPoolExecutor
import aiohttp

from .base import TTSEngine, AudioConfig, VoiceConfig

logger = logging.getLogger(__name__)

class CoquiTTSEngine(TTSEngine):
    """High-quality local TTS using Coqui TTS."""
    
    DEFAULT_MODEL = "tts_models/en/vctk/vits"
    
    # Map speaker profiles to VCTK speaker IDs
    SPEAKER_MAPPINGS = {
        'professional_host': 'p262',  # Clear, professional male
        'casual_host': 'p276',       # Warm, friendly female
        'technical_expert': 'p273',   # Articulate male
        'industry_expert': 'p254',    # Authoritative male
        'journalist': 'p236',         # Clear female
        'commentator': 'p258'         # Engaging male
    }
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        audio_config: Optional[AudioConfig] = None,
        debug: bool = False
    ):
        super().__init__(model_name or self.DEFAULT_MODEL, audio_config, debug)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.loaded = False
        self._executor = ThreadPoolExecutor(max_workers=1)
    
    async def load_model(self) -> bool:
        """Load Coqui TTS model."""
        try:
            from TTS.api import TTS
            
            if self.debug:
                logger.info(f"Loading Coqui TTS model: {self.model_name}")
                
            self.model = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: TTS(self.model_name).to(self.device)
            )
            self.loaded = True
            
            if self.debug:
                logger.info(f"Successfully loaded Coqui TTS model: {self.model_name}")
                logger.info(f"Using device: {self.device}")
                logger.info(f"Available speakers: {self.model.speakers}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load Coqui TTS model: {e}")
            return False
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using Coqui TTS."""
        try:
            if not self.loaded:
                if not await self.load_model():
                    return False
            
            # Map voice_id to VCTK speaker
            speaker = None
            if voice_config and voice_config.voice_id:
                if voice_config.voice_id in self.SPEAKER_MAPPINGS:
                    speaker = self.SPEAKER_MAPPINGS[voice_config.voice_id]
                else:
                    # If voice_id matches VCTK format directly (e.g., 'p262')
                    speaker = voice_config.voice_id

            if not speaker:
                # Default to a specific speaker if none provided
                speaker = 'p262'
            
            if self.debug:
                logger.info(f"Synthesizing text with speaker {speaker}")
                logger.info(f"Text length: {len(text)} chars")
            
            # Run synthesis in thread pool
            wav = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.model.tts(
                    text=text,
                    speaker=speaker
                )
            )
            
            # Save audio with correct sample rate
            import soundfile as sf
            sf.write(str(output_path), wav, self.model.synthesizer.output_sample_rate)
            
            if output_path.exists() and output_path.stat().st_size > 0:
                if self.debug:
                    logger.info(f"Successfully generated audio: {output_path}")
                    logger.info(f"Audio file size: {output_path.stat().st_size} bytes")
                return True
            else:
                logger.error(f"Generated audio file is empty or missing: {output_path}")
                return False
            
        except Exception as e:
            logger.error(f"Coqui TTS synthesis failed: {e}")
            if self.debug:
                import traceback
                logger.error(traceback.format_exc())
            return False
        
class BarkEngine(TTSEngine):
    """Local TTS using Bark text-to-speech."""
    
    SPEAKER_PRESETS = {
        'professional_host': 'v2/en_speaker_6',
        'casual_host': 'v2/en_speaker_8',
        'technical_expert': 'v2/en_speaker_9',
        'industry_expert': 'v2/en_speaker_3',
        'journalist': 'v2/en_speaker_7',
        'commentator': 'v2/en_speaker_4'
    }
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        audio_config: Optional[AudioConfig] = None
    ):
        super().__init__(model_name, audio_config)
        self.model = None
        self._executor = ThreadPoolExecutor(max_workers=1)
    
    async def load_model(self) -> bool:
        """Load Bark model."""
        try:
            from bark import generate_audio, preload_models
            # Preload models in thread pool
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                preload_models
            )
            self.model = generate_audio
            self.loaded = True
            logger.info("Loaded Bark TTS model")
            return True
        except Exception as e:
            logger.error(f"Failed to load Bark model: {e}")
            return False
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using Bark."""
        try:
            if not self.loaded:
                if not await self.load_model():
                    return False
            
            from bark import SAMPLE_RATE
            
            # Get speaker preset
            speaker = None
            if voice_config and voice_config.voice_id:
                speaker = self.SPEAKER_PRESETS.get(voice_config.voice_id)
            
            # Run generation in thread pool
            audio_array = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self.model(text, history_prompt=speaker)
            )
            
            # Save audio
            sf.write(output_path, audio_array, SAMPLE_RATE)
            return True
            
        except Exception as e:
            logger.error(f"Bark synthesis failed: {e}")
            return False

class OllamaTTSEngine(TTSEngine):
    """TTS using Ollama models with speech capabilities."""
    
    def __init__(
        self,
        model_name: str = "mistral-tts",
        host: str = "http://localhost:11434",
        audio_config: Optional[AudioConfig] = None
    ):
        super().__init__(model_name, audio_config)
        self.host = host
        self.loaded = True  # No model loading needed
    
    async def load_model(self) -> bool:
        """Check if model is available in Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.host}/api/tags") as response:
                    if response.status != 200:
                        return False
                    
                    data = await response.json()
                    models = [m['name'] for m in data['models']]
                    return self.model_name in models
                    
        except Exception as e:
            logger.error(f"Failed to check Ollama model: {e}")
            return False
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "model": self.model_name,
                    "prompt": f"[SPEAK]{text}",
                    "stream": False
                }
                
                async with session.post(
                    f"{self.host}/api/generate",
                    json=data
                ) as response:
                    if response.status != 200:
                        logger.error(f"Ollama API error: {response.status}")
                        return False
                    
                    data = await response.json()
                    
                    # Some Ollama models return audio as base64
                    if "audio" in data:
                        import base64
                        audio_data = base64.b64decode(data["audio"])
                        
                        # Save in temp file first to check format
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                            tmp.write(audio_data)
                            tmp_path = Path(tmp.name)
                        
                        # Convert if needed
                        try:
                            if output_path.suffix.lower() != tmp_path.suffix.lower():
                                success = await self._convert_audio(tmp_path, output_path)
                                tmp_path.unlink()
                                return success
                            else:
                                output_path.write_bytes(audio_data)
                                return True
                        finally:
                            if tmp_path.exists():
                                tmp_path.unlink()
                    
                    return False
                    
        except Exception as e:
            logger.error(f"Ollama TTS failed: {e}")
            return False
        
