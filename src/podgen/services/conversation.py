from typing import List, Dict, Any, Optional
import logging
import random
from ..models.dialogue import DialogueTurn, Dialogue
from ..models.conversation_style import SpeakerPersonality
from .llm_service import LLMService

logger = logging.getLogger(__name__)

class ConversationGenerator:
    """Generates natural dialogue using LLM capabilities."""
    
    def __init__(self):
        self.llm = LLMService()
        self.default_speakers = {
            "host": SpeakerPersonality(
                name="Alex",
                voice_id="p335",
                gender="neutral",
                style="Knowledgeable and engaging host who guides the conversation",
                verbosity=1.0,
                formality=1.0
            ),
            "expert": SpeakerPersonality(
                name="Dr. Sarah",
                voice_id="p347",
                gender="female",
                style="Technical expert who provides detailed explanations",
                verbosity=1.2,
                formality=1.5
            ),
            "questioner": SpeakerPersonality(
                name="Mike",
                voice_id="p326",
                gender="male",
                style="Asks insightful questions to clarify complex topics",
                verbosity=0.8,
                formality=0.7
            )
        }
    
    async def generate_dialogue(
        self,
        analysis: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dialogue:
        """
        Generate a natural conversation using LLM.
        """
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
        speakers = list(self.default_speakers.values())
        
        try:
            # Generate initial dialogue
            dialogue_turns = await self.llm.generate_dialogue(
                analysis,
                [s.dict() for s in speakers],
                style
            )
            
            if not dialogue_turns:
                logger.warning("LLM returned no dialogue turns, using fallback")
                return await self._generate_basic_dialogue(analysis, speakers)
            
            # Convert to DialogueTurn objects
            turns = []
            for turn in dialogue_turns:
                # Validate turn data
                if not isinstance(turn, dict) or 'speaker' not in turn or 'content' not in turn:
                    logger.warning(f"Invalid turn format: {turn}")
                    continue
                    
                # Find matching speaker
                speaker = next(
                    (s for s in speakers if s.name == turn['speaker']),
                    speakers[0]  # Default to first speaker if not found
                )
                
                turns.append(DialogueTurn(
                    speaker=speaker,
                    content=turn['content']
                ))
            
            # Ensure we have at least some dialogue
            if not turns:
                logger.warning("No valid turns created, using fallback")
                return await self._generate_basic_dialogue(analysis, speakers)
            
            # If configured, generate follow-up responses
            if config.get('interactive', True):
                enhanced_turns = []
                for i, turn in enumerate(turns):
                    enhanced_turns.append(turn)
                    
                    # Randomly add follow-ups (with decreasing probability)
                    if i < len(turns) - 1 and random.random() < 0.3 * (1 - i/len(turns)):
                        try:
                            # Generate follow-up
                            context = [
                                {
                                    'speaker': t.speaker.name,
                                    'content': t.content
                                }
                                for t in turns[max(0, i-2):i+2]
                            ]
                            
                            next_speaker = turns[i + 1].speaker
                            follow_up = await self.llm.generate_follow_up(
                                context,
                                analysis['main_topics'][0],
                                next_speaker.dict()
                            )
                            
                            if follow_up:
                                enhanced_turns.append(DialogueTurn(
                                    speaker=next_speaker,
                                    content=follow_up
                                ))
                        except Exception as e:
                            logger.warning(f"Failed to generate follow-up: {e}")
                            continue
                
                turns = enhanced_turns
            
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

