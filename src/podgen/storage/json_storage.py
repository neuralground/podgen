import json
import threading
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
        self.lock = threading.Lock()
        
        # Initialize storage files
        self.data_dir.mkdir(exist_ok=True)
        for file in [self.speakers_file, self.formats_file]:
            if not file.exists():
                file.write_text("{}")
    
    def _read_json(self, file: Path) -> Dict[str, Any]:
        """Read JSON data from file with thread safety."""
        with self.lock:
            return json.loads(file.read_text())
    
    def _write_json(self, file: Path, data: Dict[str, Any]) -> None:
        """Write JSON data to file with thread safety."""
        with self.lock:
            file.write_text(json.dumps(data, indent=2))
    
    def save_speaker(self, name: str, profile: SpeakerPersonality) -> None:
        """Save a speaker profile."""
        data = self._read_json(self.speakers_file)
        data[name] = profile.model_dump()
        self._write_json(self.speakers_file, data)
    
    def get_speaker(self, name: str) -> Optional[SpeakerPersonality]:
        """Get a speaker profile by name."""
        data = self._read_json(self.speakers_file)
        if name in data:
            return SpeakerPersonality(**data[name])
        return None
    
    def list_speakers(self) -> List[str]:
        """List all speaker names."""
        data = self._read_json(self.speakers_file)
        return list(data.keys())
    
    def delete_speaker(self, name: str) -> bool:
        """Delete a speaker profile."""
        data = self._read_json(self.speakers_file)
        if name in data:
            del data[name]
            self._write_json(self.speakers_file, data)
            return True
        return False
    
    def save_format(self, name: str, config: ConversationConfig) -> None:
        """Save a conversation format configuration."""
        data = self._read_json(self.formats_file)
        data[name] = config.model_dump()
        self._write_json(self.formats_file, data)
    
    def get_format(self, name: str) -> Optional[ConversationConfig]:
        """Get a conversation format by name."""
        data = self._read_json(self.formats_file)
        if name in data:
            return ConversationConfig(**data[name])
        return None
    
    def list_formats(self) -> List[str]:
        """List all format names."""
        data = self._read_json(self.formats_file)
        return list(data.keys())
    
    def delete_format(self, name: str) -> bool:
        """Delete a conversation format."""
        data = self._read_json(self.formats_file)
        if name in data:
            del data[name]
            self._write_json(self.formats_file, data)
            return True
        return False

