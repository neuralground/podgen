from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ConversationStyle(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    FUN = "fun"
    EDUCATIONAL = "educational"
    DEBATE = "debate"
    INTERVIEW = "interview"

class SpeakerPersonality(BaseModel):
    name: str
    voice_id: str
    gender: str = Field(..., pattern="^(male|female|neutral)$")
    style: str = Field(..., description="Speaking style characteristics")
    expertise: Optional[List[str]] = Field(default_factory=list)
    verbosity: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="Verbosity factor: 1.0 is normal, <1 is concise, >1 is verbose"
    )
    formality: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="Formality factor: 1.0 is normal, <1 is casual, >1 is formal"
    )

