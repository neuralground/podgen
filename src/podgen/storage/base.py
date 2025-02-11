from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..models.conversation_style import SpeakerPersonality
from ..models.conversation_config import ConversationConfig

class StorageBackend(ABC):
    @abstractmethod
    async def save_speaker(self, name: str, profile: SpeakerPersonality) -> None:
        pass
    
    @abstractmethod
    async def get_speaker(self, name: str) -> Optional[SpeakerPersonality]:
        pass
    
    @abstractmethod
    async def list_speakers(self) -> List[str]:
        pass
    
    @abstractmethod
    async def delete_speaker(self, name: str) -> bool:
        pass
    
    @abstractmethod
    async def save_format(self, name: str, config: ConversationConfig) -> None:
        pass
    
    @abstractmethod
    async def get_format(self, name: str) -> Optional[ConversationConfig]:
        pass
    
    @abstractmethod
    async def list_formats(self) -> List[str]:
        pass
    
    @abstractmethod
    async def delete_format(self, name: str) -> bool:
        pass

