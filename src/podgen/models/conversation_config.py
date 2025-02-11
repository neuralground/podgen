from typing import List, Optional
from pydantic import BaseModel, Field
from .conversation_style import ConversationStyle, SpeakerPersonality

class ConversationConfig(BaseModel):
    style: ConversationStyle
    num_speakers: int = Field(default=2, ge=2, le=5)
    speakers: List[SpeakerPersonality]
    max_turns: Optional[int] = Field(default=20, ge=5)
    topic_focus: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="How closely to stick to the main topic"
    )
    interaction_depth: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="How much speakers interact vs. monologue"
    )

