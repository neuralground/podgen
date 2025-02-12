import enum
from pathlib import Path
from typing import Optional, Dict, Any
import datetime

class ConversationStatus(enum.Enum):
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

class Conversation:
    """Represents a generated conversation/podcast."""
    def __init__(
        self,
        id: int,
        title: str,
        transcript: Optional[str],
        audio_path: Optional[Path],
        created_date: datetime.datetime,
        status: ConversationStatus,
        progress: float,
        error: Optional[str],
        metadata: Dict[str, Any]
    ):
        self.id = id
        self.title = title
        self.transcript = transcript
        self.audio_path = audio_path
        self.created_date = created_date
        self.status = status
        self.progress = progress
        self.error = error
        self.metadata = metadata

