"""Cloud-based TTS implementations."""

import aiohttp
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
import os
from openai import OpenAI

from .base import TTSEngine, AudioConfig, VoiceConfig

logger = logging.getLogger(__name__)

class ElevenLabsEngine(TTSEngine):
    """High-quality TTS using ElevenLabs API."""
    
    VOICE_MAPPINGS = {
        'professional_host': 'pNInz6obpgDQGcFmaJgB',  # Adam - professional, warm
        'casual_host': 'onwK4e9ZLuTAKqWW03F9',       # Josh - casual, friendly
        'technical_expert': 'ThT5KcBeYPX3keUQqHPh',   # Grace - clear, authoritative
        'industry_expert': 'txJ0herwXYrAwh7HqXOX',    # Thomas - experienced, mature
        'journalist': 'EXAVITQu4vr4xnSDxMaL',         # Emily - articulate, engaging
        'commentator': 'VR6AewLTigWG4xSOukaG'         # Daniel - insightful, natural
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        audio_config: Optional[AudioConfig] = None
    ):
        super().__init__(model_name, audio_config)
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key not provided")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "Accept": "audio/mpeg",
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def load_model(self) -> bool:
        """No model loading needed for API-based TTS."""
        self.loaded = True
        return True
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using ElevenLabs API."""
        try:
            # Get voice ID
            voice_id = voice_config.voice_id if voice_config else \
                      self.VOICE_MAPPINGS.get('casual_host')
            
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            
            # Add SSML for more natural speech patterns
            ssml_text = self._add_speech_marks(text)
            
            data = {
                "text": ssml_text,
                "model_id": self.model_name or "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": voice_config.stability if voice_config else 0.5,
                    "similarity_boost": 0.75,
                    "speaking_rate": voice_config.speed if voice_config else 1.0
                }
            }
            
            # Save as MP3 first
            mp3_path = output_path.with_suffix('.mp3')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=self.headers) as response:
                    if response.status != 200:
                        logger.error(f"ElevenLabs API error: {response.status}")
                        return False
                    
                    with open(mp3_path, 'wb') as f:
                        f.write(await response.read())
            
            # Convert to WAV if needed
            if output_path.suffix.lower() == '.wav':
                return await self._convert_audio(mp3_path, output_path)
            return True
            
        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            return False
    
    def _add_speech_marks(self, text: str) -> str:
        """Add SSML marks for more natural speech patterns."""
        # Add pauses after punctuation
        text = text.replace('. ', '.<break time="0.5s"/> ')
        text = text.replace('? ', '?<break time="0.6s"/> ')
        text = text.replace('! ', '!<break time="0.6s"/> ')
        
        # Add emphasis to quoted text
        text = text.replace('"', '<emphasis level="moderate">', 1)
        if text.count('"') % 2 == 1:
            text = text.replace('"', '</emphasis>', 1)
        
        return f'<speak>{text}</speak>'

class OpenAITTSEngine(TTSEngine):
    """High-quality TTS using OpenAI API."""
    
    VOICE_MAPPINGS = {
        'professional_host': 'onyx',      # Professional, broadcast quality
        'casual_host': 'nova',            # Warm, conversational
        'technical_expert': 'echo',       # Clear, authoritative
        'industry_expert': 'fable',       # Mature, experienced
        'journalist': 'shimmer',          # Articulate, engaging
        'commentator': 'alloy'            # Balanced, natural
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        audio_config: Optional[AudioConfig] = None
    ):
        super().__init__(model_name, audio_config)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = OpenAI(api_key=self.api_key)
    
    async def load_model(self) -> bool:
        """No model loading needed for API-based TTS."""
        self.loaded = True
        return True
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using OpenAI API."""
        try:
            # Get voice ID
            voice_id = voice_config.voice_id if voice_config else \
                      self.VOICE_MAPPINGS.get('casual_host')
            
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.audio.speech.create(
                    model=self.model_name or "tts-1-hd",
                    voice=voice_id,
                    input=text,
                    response_format="mp3",
                    speed=voice_config.speed if voice_config else 1.0
                )
            )
            
            # Save as MP3 first
            mp3_path = output_path.with_suffix('.mp3')
            response.stream_to_file(str(mp3_path))
            
            # Convert to WAV if needed
            if output_path.suffix.lower() == '.wav':
                return await self._convert_audio(mp3_path, output_path)
            return True
            
        except Exception as e:
            logger.error(f"OpenAI TTS synthesis failed: {e}")
            return False
        