# src/podgen/models/dialogue.py
from typing import List
from pydantic import BaseModel
from .conversation_style import SpeakerPersonality

class DialogueTurn(BaseModel):
    """Represents a single turn in the conversation."""
    speaker: SpeakerPersonality
    content: str
    
    class Config:
        frozen = True

class Dialogue(BaseModel):
    """Represents a complete conversation."""
    turns: List[DialogueTurn]
    
    class Config:
        frozen = True

