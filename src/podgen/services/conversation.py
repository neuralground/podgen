from typing import List, Dict, Any, Optional
import logging
import random
import json
from ..models.dialogue import DialogueTurn, Dialogue
from ..models.conversation_style import SpeakerPersonality
from ..models.speaker_profiles import (
    DEFAULT_SPEAKER_PROFILES,
    get_default_speakers,
    get_available_styles
)
from .llm_service import LLMService

logger = logging.getLogger(__name__)

class ConversationGenerator:
    """Generates natural dialogue using LLM capabilities."""
    
    def __init__(self):
        self.llm = LLMService()
    
    async def generate_dialogue(
        self,
        analysis: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dialogue:
        """Generate a natural conversation using LLM."""
        if not analysis:
            logger.warning("No analysis provided, using default structure")
            analysis = {
                'main_topics': ['General Discussion'],
                'key_points': [{'point': 'Overview'}],
                'suggested_structure': [
                    {
                        'segment': 'discussion',
                        'topics': ['General Discussion'],
                        'key_points': ['Overview']
                    }
                ]
            }
        
        # Get or create conversation configuration
        config = config or {}
        style = config.get('style', 'casual')
        target_duration = config.get('target_duration', 15)  # minutes
        
        # Get speaker roles from config
        speaker_roles = config.get('speaker_roles', [])
        if not speaker_roles:
            # Use default roles based on style
            if style == 'casual':
                speaker_roles = ['casual_host', 'industry_expert']
            elif style == 'formal':
                speaker_roles = ['professional_host', 'technical_expert']
            else:
                speaker_roles = ['professional_host', 'technical_expert']
        
        # Get speakers based on roles
        speakers = [DEFAULT_SPEAKER_PROFILES[role] for role in speaker_roles]
        
        # Calculate approximate words needed for target duration
        # Assuming average speaking rate of 150 words per minute
        target_words = target_duration * 150
        
        try:
            # Generate initial dialogue with word count guidance
            prompt = f"""Generate a natural {style} conversation between {len(speakers)} speakers discussing the following topics:

Topics: {', '.join(analysis.get('main_topics', ['General Discussion']))}

Key Points:
{json.dumps(analysis.get('key_points', [{'point': 'Overview'}]), indent=2)}

Speakers:
{chr(10).join(f"- {s.name}: {s.style}" for s in speakers)}

Important Guidelines:
1. Use EXACTLY these {len(speakers)} speakers: {', '.join(s.name for s in speakers)}
2. Total conversation should be approximately {target_words} words
3. Each turn should average 30-50 words for natural flow
4. Keep the style {style} and match each speaker's style description
5. Include natural transitions between topics

Format the response as JSON with this exact structure:
{{
  "dialogue": [
    {{"speaker": "NameOfSpeaker", "content": "What they say"}},
    {{"speaker": "AnotherSpeaker", "content": "Their response"}}
  ]
}}"""

            dialogue_turns = await self.llm.generate_dialogue(
                prompt=prompt
            )
            
            if not dialogue_turns:
                logger.warning("LLM returned no dialogue turns, using fallback")
                return await self._generate_basic_dialogue(analysis, speakers)
            
            # Convert to DialogueTurn objects
            turns = []
            used_speakers = set()
            
            for turn in dialogue_turns:
                if not isinstance(turn, dict) or 'speaker' not in turn or 'content' not in turn:
                    logger.warning(f"Invalid turn format: {turn}")
                    continue
                
                # Find matching speaker
                speaker = next(
                    (s for s in speakers if s.name == turn['speaker']),
                    None
                )
                
                if not speaker:
                    logger.warning(f"Unknown speaker in turn: {turn['speaker']}")
                    continue
                
                used_speakers.add(speaker.name)
                turns.append(DialogueTurn(
                    speaker=speaker,
                    content=turn['content']
                ))
            
            # Validate turn count and word count
            total_words = sum(len(turn.content.split()) for turn in turns)
            logger.info(f"Generated dialogue with {len(turns)} turns and {total_words} words")
            logger.info(f"Used speakers: {', '.join(used_speakers)}")
            
            if len(used_speakers) != len(speakers):
                logger.warning(
                    f"Not all speakers were used. Expected {len(speakers)}, got {len(used_speakers)}"
                )
            
            if total_words < target_words * 0.5:
                logger.warning(f"Dialogue too short ({total_words} words), regenerating...")
                return await self.generate_dialogue(analysis, config)
            
            # Ensure we have at least some dialogue
            if not turns:
                logger.warning("No valid turns created, using fallback")
                return await self._generate_basic_dialogue(analysis, speakers)
            
            return Dialogue(turns=turns)
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return await self._generate_basic_dialogue(analysis, speakers)
    
    async def _generate_basic_dialogue(
        self,
        analysis: Dict[str, Any],
        speakers: List[SpeakerPersonality]
    ) -> Dialogue:
        """Generate basic dialogue without LLM (fallback method)."""
        topics = analysis.get('main_topics', ['General Discussion'])
        key_points = analysis.get('key_points', [{'point': 'Overview'}])
        
        host = speakers[0]
        experts = speakers[1:] or [speakers[0]]
        
        turns = []
        
        # Add introduction
        turns.append(DialogueTurn(
            speaker=host,
            content=f"Welcome to our discussion about {', '.join(topics)}."
        ))
        
        # Add main points
        for point in key_points:
            speaker = experts[len(turns) % len(experts)]
            point_text = point.get('point', 'this topic') if isinstance(point, dict) else str(point)
            turns.append(DialogueTurn(
                speaker=speaker,
                content=f"An important point to consider is {point_text}."
            ))
        
        # Add conclusion
        turns.append(DialogueTurn(
            speaker=host,
            content="Thank you for joining us for this fascinating discussion."
        ))
        
        return Dialogue(turns=turns)
    