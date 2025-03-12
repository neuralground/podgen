from typing import List, Dict, Any, Optional, Tuple, Callable
from pathlib import Path
import logging
import asyncio

from ..storage.document_store import DocumentStore
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService
from ..services.audio import AudioProcessor

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]

class PodcastGenerator:
    """Main orchestrator for podcast generation."""
    
    def __init__(
        self,
        doc_store: DocumentStore,
        content_analyzer: ContentAnalyzer,
        conversation_gen: ConversationGenerator,
        tts_service: TTSService,
        audio_processor: AudioProcessor
    ):
        self.doc_store = doc_store
        self.analyzer = content_analyzer
        self.conversation = conversation_gen
        self.tts_service = tts_service
        self.debug = False
        self.audio = audio_processor

    async def generate_podcast(
        self,
        doc_ids: List[int],
        output_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
        config: Optional[Dict[str, Any]] = None,
        debug: bool = False
    ) -> Tuple[str, Path]:
        """Generate a complete podcast from documents."""
        try:
            if debug:
                logger.debug(f"Starting podcast generation with {len(doc_ids)} documents")
                logger.debug(f"Output path: {output_path}")
                
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            def report_progress(stage: str, stage_progress: float, weight: float):
                if progress_callback:
                    stage_weights = {
                        'analysis': 0.2,
                        'conversation': 0.3,
                        'synthesis': 0.4,
                        'processing': 0.1
                    }
                    base_progress = sum(stage_weights[s] for s in stage_weights if s < stage)
                    total_progress = base_progress + (stage_progress * weight)
                    progress_callback(total_progress, stage if debug else None)
            
            # Validate document IDs
            if not doc_ids:
                raise ValueError("No document IDs provided")
            
            # 1. Analyze content (20%)
            if debug:
                logger.debug("Stage 1 - Content Analysis")
            report_progress('analysis', 0.0, 0.2)
            
            try:
                analysis = await self.analyzer.analyze_documents(doc_ids)
                if not analysis:
                    raise ValueError("Content analysis returned no results")
                if debug:
                    logger.debug(f"Analysis found {len(analysis.get('main_topics', []))} topics")
                    logger.debug(f"Analysis found {len(analysis.get('key_points', []))} key points")
            except Exception as e:
                if debug:
                    logger.debug(f"Analysis failed: {str(e)}")
                analysis = {
                    'main_topics': ['Document Overview'],
                    'key_points': [{'point': 'Key document contents', 'source': 'Analysis'}],
                    'suggested_structure': [
                        {
                            'segment': 'overview',
                            'topics': ['Document Overview'],
                            'key_points': ['Document contents'],
                            'format': 'discussion'
                        }
                    ]
                }
            
            # Add system information to analysis
            analysis['llm_provider'] = self.analyzer.llm.provider if hasattr(self.analyzer.llm, 'provider') else str(type(self.analyzer.llm).__name__)
            analysis['llm_model'] = self.analyzer.llm.model if hasattr(self.analyzer.llm, 'model') else "default"
            
            report_progress('analysis', 1.0, 0.2)
            
# 2. Generate conversation (30%)
            if debug:
                logger.debug("Stage 2 - Conversation Generation")
            report_progress('conversation', 0.0, 0.3)
            
            try:
                # Generate dialogue with normal settings
                dialogue = await self.conversation.generate_dialogue(
                    analysis,
                    config
                )
                
                if not dialogue or not dialogue.turns:
                    raise ValueError("Dialogue generation returned no results")
                
                if debug:
                    logger.debug(f"Generated {len(dialogue.turns)} dialogue turns")
            except ValueError as e:
                # Fallback for dialogue generation errors
                logger.warning(f"Primary dialogue generation failed: {e}")
                
                # Only attempt fallback for specific errors
                if "Failed to generate valid conversation" in str(e) or "dialogue generation returned no results" in str(e).lower():
                    logger.info("Attempting fallback dialogue generation with simplified settings")
                    
                    # Simplify config for fallback attempt
                    fallback_config = config.copy()
                    fallback_config["style"] = "casual"  # Switch to casual style
                    fallback_config["target_duration"] = min(15, config.get("target_duration", 15))  # Reduce length if needed
                    
                    try:
                        # Try with fallback config
                        dialogue = await self.conversation.generate_dialogue(
                            analysis,
                            fallback_config
                        )
                        
                        if not dialogue or not dialogue.turns:
                            raise ValueError("Fallback dialogue generation failed to produce valid results")
                            
                        logger.info(f"Fallback dialogue generation succeeded with {len(dialogue.turns)} turns")
                    except Exception as fallback_error:
                        # Re-raise with more context
                        logger.error(f"Fallback dialogue generation also failed: {fallback_error}")
                        raise ValueError(f"Dialogue generation failed after fallback attempt") from e
                else:
                    # Re-raise original error if not specifically a dialogue validation issue
                    raise
            
            report_progress('conversation', 1.0, 0.3)

            # Build transcript
            transcript = self._format_transcript(dialogue)
            if debug:
                logger.debug(f"Generated transcript ({len(transcript)} chars)")
                   
            # 3. Synthesize speech (40%)
            if debug:
                logger.debug("Stage 3 - Speech Synthesis")
            report_progress('synthesis', 0.0, 0.4)
            
            audio_segments = []
            total_turns = len(dialogue.turns)
            
            for i, turn in enumerate(dialogue.turns):
                try:
                    if debug:
                        logger.debug(f"Synthesizing turn {i+1}/{total_turns} for {turn.speaker.name}")
                    segment = await self.tts_service.synthesize_turn(
                        turn,
                        output_path.parent / f"segment_{i}.wav"
                    )
                    if segment and segment.exists():
                        audio_segments.append(segment)
                        if debug:
                            logger.debug(f"Successfully generated segment {i+1}")
                except Exception as e:
                    if debug:
                        logger.debug(f"Failed to synthesize turn {i+1}: {str(e)}")
                    logger.error(f"TTS failed for speaker {turn.speaker.name}: {str(e)}")
                    # Try with a different voice if available
                    try:
                        if debug:
                            logger.debug(f"Retrying with fallback voice...")
                        
                        # Use a different voice mapping
                        fallback_voice = 'casual_host'  # Default fallback
                        if turn.speaker.name == 'casual_host':
                            fallback_voice = 'professional_host'
                                
                        # Get the ElevenLabs voice ID for the fallback voice
                        elevenlabs_voice_id = None
                        if hasattr(self.tts_service, 'get_default_engine'):
                            engine = self.tts_service.get_default_engine()
                            if hasattr(engine, 'VOICE_MAPPINGS'):
                                elevenlabs_voice_id = engine.VOICE_MAPPINGS.get(fallback_voice)
                                logger.debug(f"Using fallback ElevenLabs voice ID: {elevenlabs_voice_id}")
                        
                        if not elevenlabs_voice_id:
                            # Fallback to a hardcoded valid voice ID if all else fails
                            elevenlabs_voice_id = "TxGEqnHWrfWFTfGW9XjX"  # Josh voice
                            logger.debug(f"Using hardcoded fallback voice ID: {elevenlabs_voice_id}")
                        
                        # Create fallback voice config
                        fallback_config = VoiceConfig(
                            voice_id=elevenlabs_voice_id,
                            speed=0.9,
                            stability=0.7
                        )
                        
                        # Retry synthesis with fallback voice
                        audio_path = await self.tts_service.synthesize_speech(
                            text=turn.content,
                            output_dir=output_path.parent,
                            voice_config=fallback_config,
                            debug=debug
                        )
                        
                        if audio_path:
                            audio_segments.append(audio_path)
                            if debug:
                                logger.debug(f"Successfully synthesized with fallback voice")
                    except Exception as fallback_error:
                        logger.error(f"Fallback TTS also failed: {str(fallback_error)}")
                    continue
                
                report_progress('synthesis', (i + 1) / total_turns, 0.4)
            
            if not audio_segments:
                raise ValueError("No audio segments were generated successfully")
            
            # 4. Combine audio (10%)
            if debug:
                logger.debug("Stage 4 - Audio Processing")
            report_progress('processing', 0.0, 0.1)
            
            try:
                final_podcast = await self.audio.combine_audio_files(
                    audio_segments,
                    output_path,
                    debug=debug
                )
            except Exception as e:
                if debug:
                    logger.debug(f"Failed to combine audio: {str(e)}")
                raise
            finally:
                # Clean up temporary files
                for segment in audio_segments:
                    try:
                        segment.unlink()
                    except Exception as e:
                        if debug:
                            logger.debug(f"Failed to delete temp file {segment}: {str(e)}")
            
            report_progress('processing', 1.0, 0.1)
            
            if not final_podcast or not final_podcast.exists():
                raise ValueError("Final podcast file was not created")
            
            if debug:
                logger.debug("Podcast generation complete!")
            
            return transcript, final_podcast
            
        except Exception as e:
            if debug:
                logger.debug(f"Podcast generation failed: {str(e)}")
            raise

    def _format_transcript(self, dialogue) -> str:
        """Format dialogue into a readable transcript."""
        if not dialogue or not dialogue.turns:
            return "No transcript available."
            
        lines = []
        for turn in dialogue.turns:
            if turn.speaker and turn.content:
                lines.extend([
                    f"**{turn.speaker.name}**:",
                    turn.content,
                    ""  # Blank line between turns
                ])
        
        return "\n".join(lines) if lines else "No transcript available."
