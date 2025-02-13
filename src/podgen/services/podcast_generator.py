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
        self.tts = tts_service
        self.audio = audio_processor
    
    async def generate_podcast(
        self,
        doc_ids: List[int],
        output_path: Path,
        progress_callback: Optional[ProgressCallback] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Path]:
        """
        Generate a complete podcast from documents.
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            def report_progress(stage: str, stage_progress: float, weight: float):
                if progress_callback:
                    # Calculate overall progress based on stage weights
                    stage_weights = {
                        'analysis': 0.2,
                        'conversation': 0.3,
                        'synthesis': 0.4,
                        'processing': 0.1
                    }
                    
                    base_progress = sum(
                        stage_weights[s] 
                        for s in stage_weights 
                        if s < stage
                    )
                    
                    total_progress = base_progress + (stage_progress * weight)
                    progress_callback(total_progress)
            
            # Validate document IDs
            if not doc_ids:
                raise ValueError("No document IDs provided")
                
            # Analyze content (20%)
            logger.info("Analyzing documents...")
            report_progress('analysis', 0.0, 0.2)
            
            try:
                analysis = await self.analyzer.analyze_documents(doc_ids)
                if not analysis:
                    raise ValueError("Content analysis returned no results")
            except Exception as e:
                logger.error(f"Analysis failed: {e}")
                # Create minimal analysis structure
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
            
            report_progress('analysis', 1.0, 0.2)
            
            # Generate conversation (30%)
            logger.info("Generating conversation...")
            report_progress('conversation', 0.0, 0.3)
            
            try:
                dialogue = await self.conversation.generate_dialogue(
                    analysis,
                    config or {}
                )
                if not dialogue or not dialogue.turns:
                    raise ValueError("Dialogue generation returned no results")
            except Exception as e:
                logger.error(f"Dialogue generation failed: {e}")
                raise
            
            report_progress('conversation', 1.0, 0.3)
            
            # Build transcript
            transcript = self._format_transcript(dialogue)
            
            # Synthesize speech (40%)
            logger.info("Synthesizing speech...")
            report_progress('synthesis', 0.0, 0.4)
            
            audio_segments = []
            total_turns = len(dialogue.turns)
            
            for i, turn in enumerate(dialogue.turns):
                try:
                    segment = await self.tts.synthesize_turn(
                        turn,
                        output_path.parent / f"segment_{i}.wav"
                    )
                    if segment and segment.exists():
                        audio_segments.append(segment)
                except Exception as e:
                    logger.error(f"Failed to synthesize turn {i}: {e}")
                    continue
                
                report_progress('synthesis', (i + 1) / total_turns, 0.4)
            
            if not audio_segments:
                raise ValueError("No audio segments were generated successfully")
            
            # Combine audio (10%)
            logger.info("Processing audio...")
            report_progress('processing', 0.0, 0.1)
            
            try:
                final_podcast = await self.audio.combine_audio_files(
                    audio_segments,
                    output_path
                )
            except Exception as e:
                logger.error(f"Failed to combine audio: {e}")
                raise
            finally:
                # Clean up temporary files
                for segment in audio_segments:
                    try:
                        segment.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file {segment}: {e}")
            
            report_progress('processing', 1.0, 0.1)
            
            if not final_podcast or not final_podcast.exists():
                raise ValueError("Final podcast file was not created")
            
            return transcript, final_podcast
            
        except Exception as e:
            logger.error(f"Podcast generation failed: {e}")
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

