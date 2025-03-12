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
    
    # Updated with valid ElevenLabs voice IDs
    VOICE_MAPPINGS = {
        'professional_host': 'ErXwobaYiN019PkySvjV',  # Antoni - professional
        'casual_host': 'TxGEqnHWrfWFTfGW9XjX',        # Josh - casual, friendly
        'technical_expert': 'MF3mGyEYCl7XYWbV9V6O',   # Elli - clear, technical
        'industry_expert': 'VR6AewLTigWG4xSOukaG',    # Daniel - experienced
        'journalist': 'EXAVITQu4vr4xnSDxMaL',         # Emily - articulate
        'commentator': 'yoZ06aMxZJJ28mfd3POQ'         # Sam - conversational
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
    
    def get_elevenlabs_voice_id(self, voice_id: str) -> str:
        """Map a voice ID to an ElevenLabs voice ID."""
        # Map local voice IDs to ElevenLabs voice IDs
        local_to_elevenlabs_mapping = {
            # Map local voice IDs to ElevenLabs voice IDs
            "p326": self.VOICE_MAPPINGS.get('casual_host'),        # Sam -> Josh
            "p330": self.VOICE_MAPPINGS.get('industry_expert'),    # Michael -> Thomas
            "p335": self.VOICE_MAPPINGS.get('professional_host'),  # Alex -> Adam
            "p340": self.VOICE_MAPPINGS.get('journalist'),         # Emma -> Emily
            "p347": self.VOICE_MAPPINGS.get('technical_expert'),   # Dr. Sarah -> Grace
            "p339": self.VOICE_MAPPINGS.get('commentator')         # Fallback -> Daniel
        }
        
        # Use mapped voice ID if it's a local ID, otherwise use the original
        return local_to_elevenlabs_mapping.get(voice_id, voice_id)
    
    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice_config: Optional[VoiceConfig] = None
    ) -> bool:
        """Generate speech using ElevenLabs API."""
        try:
            # Get voice ID
            original_voice_id = voice_config.voice_id if voice_config else \
                      self.VOICE_MAPPINGS.get('casual_host')
            
            voice_id = self.get_elevenlabs_voice_id(original_voice_id)
            
            logger.debug(f"Using voice ID: {voice_id} (original: {original_voice_id})")
            
            # Check if text is too long - ElevenLabs has limits
            if len(text) > 5000:
                logger.warning(f"Text length ({len(text)}) exceeds recommended limit. Truncating to 5000 chars.")
                text = text[:5000]
            
            # Check if text is empty
            if not text or text.strip() == "":
                logger.warning("Empty text provided for synthesis, skipping")
                return False
                
            # Clean the text to avoid common issues
            text = text.replace('"', "'").replace('\n\n', '\n').strip()
            
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            
            # Add SSML for more natural speech patterns
            ssml_text = self._add_speech_marks(text)
            
            # Ensure model name is valid
            model_id = self.model_name or "eleven_monolingual_v1"
            
            # Map model names to ElevenLabs model IDs if needed
            model_mapping = {
                "eleven_monolingual_v1": "eleven_monolingual_v1",
                "eleven_multilingual_v1": "eleven_multilingual_v1",
                "eleven_multilingual_v2": "eleven_multilingual_v2",
                "eleven_turbo_v2": "eleven_turbo_v2"
            }
            
            # Use the mapped model ID if available, otherwise use the original
            model_id = model_mapping.get(model_id, model_id)
            
            logger.debug(f"Using ElevenLabs model: {model_id}")
            
            data = {
                "text": ssml_text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": voice_config.stability if voice_config else 0.5,
                    "similarity_boost": 0.75,
                    "speaking_rate": voice_config.speed if voice_config else 1.0
                }
            }
            
            # Save as MP3 first
            mp3_path = output_path.with_suffix('.mp3')
            
            # Implement retry logic
            max_retries = 3
            retry_delay = 2  # seconds
            
            for retry in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=data, headers=self.headers) as response:
                            if response.status != 200:
                                error_text = await response.text()
                                logger.error(f"ElevenLabs API error: {response.status}")
                                logger.error(f"Error details: {error_text}")
                                
                                if retry < max_retries - 1:
                                    logger.info(f"Retrying in {retry_delay} seconds... (Attempt {retry+1}/{max_retries})")
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2  # Exponential backoff
                                    continue
                                return False
                            
                            with open(mp3_path, 'wb') as f:
                                f.write(await response.read())
                            
                            # Success, break out of retry loop
                            break
                except Exception as e:
                    logger.error(f"ElevenLabs API request failed: {e}")
                    if retry < max_retries - 1:
                        logger.info(f"Retrying in {retry_delay} seconds... (Attempt {retry+1}/{max_retries})")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        logger.error("Max retries reached, giving up")
                        return False
            
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
        