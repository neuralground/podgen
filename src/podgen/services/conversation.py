from typing import List, Dict, Any, Optional
import logging
import random
from podgen.models.dialogue import DialogueTurn, Dialogue
from podgen.models.conversation_style import SpeakerPersonality
from podgen.models.speaker_profiles import (
    DEFAULT_SPEAKER_PROFILES,
    get_default_speakers,
    get_available_styles
)
from podgen.services.llm import LLMProvider, create_llm_service, PromptBuilder

logger = logging.getLogger(__name__)

class ConversationGenerator:
    """Generates natural dialogue using LLM capabilities."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """Initialize with optional LLM configuration."""
        if llm_provider and llm_model:
            self.llm = create_llm_service(
                provider=llm_provider,
                model_name=llm_model,
                api_key=api_key
            )
        else:
            self.llm = create_llm_service(
                provider=LLMProvider.OPENAI,
                model_name="gpt-4",
                api_key=api_key
            )

    async def generate_dialogue(
        self,
        analysis: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dialogue:
        """Generate a natural conversation using LLM."""
        # Get configuration
        config = config or {}
        style = config.get('style', 'casual')
        target_duration = config.get('target_duration', 15)  # minutes
        
        # Get speaker roles and create speaker instances
        speaker_roles = config.get('speaker_roles', [])
        if not speaker_roles:
            if style == 'casual':
                speaker_roles = ['casual_host', 'industry_expert']
            elif style == 'formal':
                speaker_roles = ['professional_host', 'technical_expert']
            else:
                speaker_roles = ['professional_host', 'technical_expert']
        
        # Get speakers based on roles
        speakers = [DEFAULT_SPEAKER_PROFILES[role] for role in speaker_roles]
        
        # Calculate target metrics
        target_words = target_duration * 150  # 150 words per minute
        min_turns = max(10, target_duration * 2)  # At least 2 turns per minute
        min_words_per_turn = 40  # Minimum words per speaking turn
        max_retries = 3  # Maximum number of regeneration attempts
        
        try:
            # Extract content from analysis
            topics = analysis.get('main_topics', ['General Discussion'])
            key_points = analysis.get('key_points', [])
            
            # Generate with improved retry logic
            remaining_retries = max_retries
            current_temperature = 0.7  # Start with default temperature
            
            while remaining_retries > 0:
                try:
                    # Adjust temperature based on remaining retries
                    if remaining_retries < max_retries:
                        current_temperature = min(0.9, current_temperature + 0.1)
                    
                    # Generate dialogue using prompt builder
                    prompt = PromptBuilder.build_dialogue_prompt(
                        style=style,
                        target_duration=target_duration,
                        speakers=speakers,
                        topics=topics,
                        key_points=key_points
                    )
                    
                    dialogue_turns = await self.llm.generate_dialogue(
                        prompt=prompt,
                        system_prompt="Generate a natural, detailed conversation in valid JSON format. Each turn should be substantial.",
                        temperature=current_temperature
                    )
                    
                    # Validate response
                    if not dialogue_turns:
                        logger.warning(f"Attempt {max_retries - remaining_retries + 1}: No dialogue generated")
                        remaining_retries -= 1
                        continue
                    
                    # Process turns with validation
                    turns = []
                    total_words = 0
                    used_speakers = set()
                    
                    for turn in dialogue_turns:
                        if not isinstance(turn, dict) or 'speaker' not in turn or 'content' not in turn:
                            continue
                        
                        # Find matching speaker with fuzzy matching
                        speaker = next(
                            (s for s in speakers if turn['speaker'].lower() in s.name.lower()),
                            None
                        )
                        if not speaker:
                            continue
                        
                        content = turn['content'].strip()
                        word_count = len(content.split())
                        
                        # Try to expand short turns if needed
                        if word_count < min_words_per_turn and word_count >= 15:
                            if any(point['point'] in content for point in key_points):
                                content += f" This connects directly to our discussion about {random.choice(topics)}."
                            word_count = len(content.split())
                        
                        if word_count >= min_words_per_turn:
                            used_speakers.add(speaker.name)
                            turns.append(DialogueTurn(speaker=speaker, content=content))
                            total_words += word_count
                    
                    # Validate metrics
                    if (len(turns) >= min_turns and 
                        total_words >= target_words * 0.8 and  # Allow 20% below target
                        len(used_speakers) == len(speakers)):
                        logger.info(f"Generated valid conversation: {len(turns)} turns, {total_words} words")
                        return Dialogue(turns=turns)
                    
                    logger.warning(
                        f"Attempt {max_retries - remaining_retries + 1}: Generated conversation too short "
                        f"({len(turns)} turns, {total_words} words, {len(used_speakers)}/{len(speakers)} speakers)"
                    )
                    
                    # Enhance prompt for retry
                    if remaining_retries > 1:
                        prompt += (
                            f"\n\nIMPORTANT: Need more detailed responses. "
                            f"Target metrics: {target_words} words, {min_turns} turns minimum. "
                            f"Each turn should be substantial."
                        )
                    
                    remaining_retries -= 1
                    
                except Exception as e:
                    logger.error(f"Error during generation attempt: {e}")
                    remaining_retries -= 1
                    continue
            
            raise ValueError(f"Failed to generate valid conversation after {max_retries} attempts")
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            raise

    def _log_dialogue_metrics(self, turns: List[DialogueTurn]) -> None:
        """Log metrics about the generated dialogue."""
        if not turns:
            return
            
        total_words = sum(len(turn.content.split()) for turn in turns)
        avg_words = total_words / len(turns)
        speakers = set(turn.speaker.name for turn in turns)
        
        logger.info(f"Dialogue metrics:")
        logger.info(f"- Total turns: {len(turns)}")
        logger.info(f"- Total words: {total_words}")
        logger.info(f"- Average words per turn: {avg_words:.1f}")
        logger.info(f"- Unique speakers: {len(speakers)}")
        logger.info(f"- Speakers: {', '.join(speakers)}")
