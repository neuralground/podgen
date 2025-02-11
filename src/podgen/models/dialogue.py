from typing import List
from pydantic import BaseModel
from .speaker import Speaker

class DialogueTurn(BaseModel):
    """Represents a single turn in the conversation."""
    speaker: Speaker
    content: str
    
    class Config:
        frozen = True

class Dialogue(BaseModel):
    """Represents a complete conversation."""
    turns: List[DialogueTurn]
    
    class Config:
        frozen = True

