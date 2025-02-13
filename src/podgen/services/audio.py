from pathlib import Path
from typing import List
import subprocess
import logging
import asyncio

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing tasks like combining files and adding effects."""
    
    async def combine_audio_files(
        self, 
        audio_files: List[Path], 
        output_file: Path,
        crossfade_duration: float = 0.5
    ) -> Path:
        """
        Combines multiple audio files into a single file with crossfading.
        
        Args:
            audio_files: List of paths to input audio files
            output_file: Path for the combined output file
            crossfade_duration: Duration of crossfade between segments in seconds
            
        Returns:
            Path to the combined audio file
        """
        try:
            # Create complex ffmpeg filter for crossfading
            filter_complex = []
            for i in range(len(audio_files) - 1):
                filter_complex.extend([
                    f'[{i}][{i+1}]acrossfade=d={crossfade_duration}[a{i}];'
                ])
            
            # Build ffmpeg command
            cmd = ['ffmpeg', '-y', '-loglevel', 'error']  # Only show errors
            
            # Add input files
            for audio_file in audio_files:
                cmd.extend(['-i', str(audio_file)])
            
            # Add filter complex and output
            cmd.extend([
                '-filter_complex', ''.join(filter_complex),
                str(output_file)
            ])
            
            # Execute ffmpeg in a thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    check=True,
                    capture_output=True,  # Capture output for error logging
                    text=True
                )
            )
            
            # Check if output file was created
            if not output_file.exists():
                raise RuntimeError("Output file was not created")
                
            return output_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to combine audio files: {e}")
            if e.stderr:
                logger.error(f"FFmpeg error output: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error combining audio files: {e}")
            raise

