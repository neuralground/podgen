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
        
        # Calculate target metrics based on duration
        target_words = target_duration * 150  # 150 words per minute
        min_words_per_turn = 75  # Increased minimum words per turn
        optimal_turns = max(int(target_words / min_words_per_turn), 10)
        
        try:
            # Extract content from analysis
            topics = analysis.get('main_topics', ['General Discussion'])
            key_points = analysis.get('key_points', [])
            
            # Start with shorter target for first attempt
            initial_target = max(target_words * 0.8, 500)  # Start with 80% of target
            current_target = initial_target
            max_attempts = 5  # Increased from 3 to 5 attempts
            current_temperature = 0.7
            
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Dialogue generation attempt {attempt + 1}")
                    logger.info(f"Target words: {int(current_target)}")
                    
                    # Adjust temperature based on remaining attempts
                    if attempt > 0:
                        current_temperature = min(0.9, current_temperature + 0.05)
                    
                    # Generate with updated word target
                    config_with_target = {
                        **config,
                        'target_words': int(current_target),
                        'attempt': attempt + 1,
                        'max_attempts': max_attempts
                    }
                    
                    # Generate dialogue using prompt builder
                    prompt = PromptBuilder.build_dialogue_prompt(
                        style=style,
                        target_duration=target_duration,
                        target_words=int(current_target),
                        optimal_turns=optimal_turns,
                        speakers=speakers,
                        topics=topics,
                        key_points=key_points,
                        attempt=attempt + 1,
                        max_attempts=max_attempts
                    )
                    
                    dialogue_turns = await self.llm.generate_dialogue(
                        prompt=prompt,
                        system_prompt="Generate natural, detailed conversation in valid JSON format. Each turn must be substantial.",
                        temperature=current_temperature
                    )
                    
                    if not dialogue_turns:
                        logger.warning(f"Attempt {attempt + 1}: No dialogue generated")
                        continue
                    
                    # Process turns with validation
                    turns = []
                    total_words = 0
                    used_speakers = set()
                    
                    # Adjust validation thresholds based on model
                    is_o1_model = hasattr(self.llm, 'model') and str(self.llm.model).startswith('o1')
                    min_words_per_turn = 30 if is_o1_model else 75  # Even more lenient for o1
                    min_turn_ratio = 0.5 if is_o1_model else 0.8    # More lenient completion threshold
                    max_sequential_same_speaker = 2                  # Prevent monologues
                    
                    current_speaker = None
                    same_speaker_count = 0
                    
                    for turn in dialogue_turns:
                        if not isinstance(turn, dict) or 'speaker' not in turn or 'content' not in turn:
                            logger.warning("Invalid turn format")
                            continue
                        
                        # Try flexible speaker matching
                        speaker_name = turn['speaker'].strip().lower()
                        speaker = None
                        for s in speakers:
                            if s.name.lower() in speaker_name or speaker_name in s.name.lower():
                                speaker = s
                                break
                        
                        if not speaker:
                            logger.warning(f"Could not match speaker: {turn['speaker']}")
                            continue
                        
                        # Check for too many sequential turns by same speaker
                        if speaker == current_speaker:
                            same_speaker_count += 1
                            if same_speaker_count > max_sequential_same_speaker:
                                logger.warning("Too many sequential turns by same speaker")
                                continue
                        else:
                            same_speaker_count = 1
                            current_speaker = speaker
                        
                        content = turn['content'].strip()
                        word_count = len(content.split())
                        
                        # Allow shorter turns if they're substantive
                        if word_count < min_words_per_turn:
                            # Check if content seems substantive despite length
                            sentences = content.split('.')
                            if len(sentences) >= 2 and word_count >= min_words_per_turn * 0.7:
                                logger.info(f"Accepting shorter but substantive turn: {word_count} words")
                            else:
                                logger.warning(f"Turn too short: {word_count} words")
                                continue
                        
                        used_speakers.add(speaker.name)
                        turns.append(DialogueTurn(speaker=speaker, content=content))
                        total_words += word_count
                        
                        logger.info(f"Added turn: {speaker.name}, {word_count} words")
                    
                    # Log validation metrics
                    logger.info(f"Generated turns: {len(turns)}")
                    logger.info(f"Total words: {total_words}")
                    logger.info(f"Target words: {target_words}")
                    logger.info(f"Speakers used: {len(used_speakers)}/{len(speakers)}")
                    
                    # Check if we've met our requirements
                    if (len(turns) >= optimal_turns * min_turn_ratio and
                        total_words >= target_words * min_turn_ratio and
                        len(used_speakers) == len(speakers)):
                        logger.info(f"Generated valid conversation: {len(turns)} turns, {total_words} words")
                        return Dialogue(turns=turns)
                    else:
                        logger.warning(
                            f"Generated conversation too short or incomplete:\n"
                            f"Turns: {len(turns)} vs required {optimal_turns * min_turn_ratio}\n"
                            f"Words: {total_words} vs required {target_words * min_turn_ratio}\n"
                            f"Speakers: {len(used_speakers)} vs required {len(speakers)}"
                        )

                    # Increase target for next attempt
                    current_target = min(current_target * 1.25, target_words * 1.2)
                    
                    # Last attempt - try with maximum target
                    if attempt == max_attempts - 2:
                        current_target = target_words * 1.2
                    
                except Exception as e:
                    logger.error(f"Error during generation attempt: {e}")
                    if attempt == max_attempts - 1:
                        raise
                    continue
            
            raise ValueError(f"Failed to generate valid conversation after {max_attempts} attempts")
            
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
