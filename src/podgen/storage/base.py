from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from ..models.conversation_style import SpeakerPersonality
from ..models.conversation_config import ConversationConfig

class StorageBackend(ABC):
    @abstractmethod
    def save_speaker(self, name: str, profile: SpeakerPersonality) -> None:
        pass
    
    @abstractmethod
    def get_speaker(self, name: str) -> Optional[SpeakerPersonality]:
        pass
    
    @abstractmethod
    def list_speakers(self) -> List[str]:
        pass
    
    @abstractmethod
    def delete_speaker(self, name: str) -> bool:
        pass
    
    @abstractmethod
    def save_format(self, name: str, config: ConversationConfig) -> None:
        pass
    
    @abstractmethod
    def get_format(self, name: str) -> Optional[ConversationConfig]:
        pass
    
    @abstractmethod
    def list_formats(self) -> List[str]:
        pass
    
    @abstractmethod
    def delete_format(self, name: str) -> bool:
        pass

