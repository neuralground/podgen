from pydantic import BaseModel

class Speaker(BaseModel):
    """Represents a speaker in the podcast."""
    name: str
    voice_id: str
    personality: str
    
    class Config:
        frozen = True

