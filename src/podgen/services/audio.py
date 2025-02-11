from pathlib import Path
from typing import List
import subprocess
import logging

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing tasks like combining files and adding effects."""
    
    def combine_audio_files(
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
            cmd = ['ffmpeg', '-y']  # -y to overwrite output file
            for audio_file in audio_files:
                cmd.extend(['-i', str(audio_file)])
            
            cmd.extend([
                '-filter_complex', ''.join(filter_complex),
                str(output_file)
            ])
            
            # Execute ffmpeg
            subprocess.run(cmd, check=True)
            return output_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to combine audio files: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error combining audio files: {e}")
            raise

