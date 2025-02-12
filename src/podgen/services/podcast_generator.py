# src/podgen/services/podcast_generator.py
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
        config: Dict[str, Any] = None
    ) -> Tuple[str, Path]:
        """
        Generate a complete podcast from documents.
        
        Args:
            doc_ids: List of document IDs to include
            output_path: Where to save the final podcast
            progress_callback: Optional callback for progress updates (0.0 to 1.0)
            config: Optional generation configuration
            
        Returns:
            Tuple of (transcript text, audio file path)
        """
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create progress tracker
            def report_progress(stage: str, stage_progress: float, weight: float):
                if progress_callback:
                    # Calculate overall progress based on stage weights
                    stage_weights = {
                        'analysis': 0.2,
                        'conversation': 0.3,
                        'synthesis': 0.4,
                        'processing': 0.1
                    }
                    
                    # Get base progress for completed stages
                    base_progress = sum(
                        stage_weights[s] 
                        for s in stage_weights 
                        if s < stage
                    )
                    
                    # Add current stage progress
                    total_progress = base_progress + (stage_progress * weight)
                    progress_callback(total_progress)
            
            # Analyze content (20%)
            logger.info("Analyzing documents...")
            report_progress('analysis', 0.0, 0.2)
            
            analysis = await self.analyzer.analyze_documents(doc_ids)
            report_progress('analysis', 1.0, 0.2)
            
            # Generate conversation (30%)
            logger.info("Generating conversation...")
            report_progress('conversation', 0.0, 0.3)
            
            dialogue = self.conversation.generate_dialogue(
                analysis['suggested_structure'],
                config
            )
            report_progress('conversation', 1.0, 0.3)
            
            # Build transcript
            transcript = self._format_transcript(dialogue)
            
            # Synthesize speech (40%)
            logger.info("Synthesizing speech...")
            report_progress('synthesis', 0.0, 0.4)
            
            audio_segments = []
            for i, turn in enumerate(dialogue.turns):
                segment = await self.tts.synthesize_turn(
                    turn,
                    output_path.parent / f"segment_{i}.wav"
                )
                audio_segments.append(segment)
                report_progress('synthesis', (i + 1) / len(dialogue.turns), 0.4)
            
            # Combine audio (10%)
            logger.info("Processing audio...")
            report_progress('processing', 0.0, 0.1)
            
            final_podcast = self.audio.combine_audio_files(
                audio_segments,
                output_path
            )
            
            # Clean up temporary files
            for segment in audio_segments:
                segment.unlink()
            
            report_progress('processing', 1.0, 0.1)
            
            return transcript, final_podcast
            
        except Exception as e:
            logger.error(f"Podcast generation failed: {e}")
            raise
    
    def _format_transcript(self, dialogue) -> str:
        """Format dialogue into a readable transcript."""
        lines = []
        for turn in dialogue.turns:
            lines.extend([
                f"**{turn.speaker.name}**:",
                turn.content,
                ""  # Blank line between turns
            ])
        return "\n".join(lines)

