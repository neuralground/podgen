from typing import Dict, List
from ..models.conversation_style import SpeakerPersonality

DEFAULT_SPEAKER_PROFILES: Dict[str, SpeakerPersonality] = {
    "professional_host": SpeakerPersonality(
        name="Alex",
        voice_id="p335",
        gender="neutral",
        style="Professional broadcast host with clear articulation and engaging presence",
        expertise=["broadcasting", "interviewing"],
        verbosity=1.0,
        formality=1.2
    ),
    
    "casual_host": SpeakerPersonality(
        name="Sam",
        voice_id="p326",
        gender="neutral",
        style="Casual and friendly podcast host with a conversational style",
        expertise=["conversation", "storytelling"],
        verbosity=1.1,
        formality=0.8
    ),
    
    "technical_expert": SpeakerPersonality(
        name="Dr. Sarah",
        voice_id="p347",
        gender="female",
        style="Technical expert who explains complex topics clearly",
        expertise=["technical analysis", "research"],
        verbosity=1.2,
        formality=1.5
    ),
    
    "industry_expert": SpeakerPersonality(
        name="Michael",
        voice_id="p330",
        gender="male",
        style="Industry veteran with practical experience and insights",
        expertise=["business", "industry trends"],
        verbosity=1.0,
        formality=1.1
    ),
    
    "journalist": SpeakerPersonality(
        name="Emma",
        voice_id="p340",
        gender="female",
        style="Investigative journalist who asks probing questions",
        expertise=["investigation", "current events"],
        verbosity=0.9,
        formality=1.2
    ),
    
    "commentator": SpeakerPersonality(
        name="James",
        voice_id="p328",
        gender="male",
        style="Insightful commentator who provides analysis and perspective",
        expertise=["analysis", "commentary"],
        verbosity=1.1,
        formality=1.0
    )
}

# Define default role combinations for different conversation styles
DEFAULT_ROLE_COMBINATIONS: Dict[str, List[str]] = {
    "casual": ["casual_host", "industry_expert"],
    "formal": ["professional_host", "technical_expert"],
    "interview": ["professional_host", "industry_expert"],
    "panel": ["professional_host", "technical_expert", "industry_expert"],
    "debate": ["professional_host", "commentator", "commentator"],
    "educational": ["casual_host", "technical_expert"]
}

def get_default_speakers(style: str = "casual") -> List[SpeakerPersonality]:
    """Get default speakers for a conversation style."""
    role_keys = DEFAULT_ROLE_COMBINATIONS.get(style, DEFAULT_ROLE_COMBINATIONS["casual"])
    return [DEFAULT_SPEAKER_PROFILES[role] for role in role_keys]

def get_available_styles() -> List[str]:
    """Get list of available conversation styles."""
    return list(DEFAULT_ROLE_COMBINATIONS.keys())

def get_available_speaker_roles() -> List[str]:
    """Get list of available speaker roles."""
    return list(DEFAULT_SPEAKER_PROFILES.keys())

