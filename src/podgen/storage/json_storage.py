import json
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..models.conversation_style import SpeakerPersonality
from ..models.conversation_config import ConversationConfig
from .base import StorageBackend

class JSONStorage(StorageBackend):
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.speakers_file = data_dir / "speakers.json"
        self.formats_file = data_dir / "formats.json"
        self.lock = asyncio.Lock()
        
        # Initialize storage files
        self.data_dir.mkdir(exist_ok=True)
        for file in [self.speakers_file, self.formats_file]:
            if not file.exists():
                file.write_text("{}")
    
    async def _read_json(self, file: Path) -> Dict[str, Any]:
        async with self.lock:
            return json.loads(file.read_text())
    
    async def _write_json(self, file: Path, data: Dict[str, Any]) -> None:
        async with self.lock:
            file.write_text(json.dumps(data, indent=2))
    
    async def save_speaker(self, name: str, profile: SpeakerPersonality) -> None:
        data = await self._read_json(self.speakers_file)
        data[name] = profile.dict()
        await self._write_json(self.speakers_file, data)
    
    async def get_speaker(self, name: str) -> Optional[SpeakerPersonality]:
        data = await self._read_json(self.speakers_file)
        if name in data:
            return SpeakerPersonality(**data[name])
        return None
    
    async def list_speakers(self) -> List[str]:
        data = await self._read_json(self.speakers_file)
        return list(data.keys())
    
    async def delete_speaker(self, name: str) -> bool:
        data = await self._read_json(self.speakers_file)
        if name in data:
            del data[name]
            await self._write_json(self.speakers_file, data)
            return True
        return False
    
    async def save_format(self, name: str, config: ConversationConfig) -> None:
        data = await self._read_json(self.formats_file)
        data[name] = config.dict()
        await self._write_json(self.formats_file, data)
    
    async def get_format(self, name: str) -> Optional[ConversationConfig]:
        data = await self._read_json(self.formats_file)
        if name in data:
            return ConversationConfig(**data[name])
        return None
    
    async def list_formats(self) -> List[str]:
        data = await self._read_json(self.formats_file)
        return list(data.keys())
    
    async def delete_format(self, name: str) -> bool:
        data = await self._read_json(self.formats_file)
        if name in data:
            del data[name]
            await self._write_json(self.formats_file, data)
            return True
        return False

