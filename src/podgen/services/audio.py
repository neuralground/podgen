"""Enhanced audio processing with validation."""

import wave
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def get_audio_duration(file_path: Path) -> Optional[float]:
    """Get duration of a WAV file in seconds."""
    try:
        with wave.open(str(file_path), 'rb') as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        logger.error(f"Failed to get audio duration for {file_path}: {e}")
        return None

class AudioProcessor:
    """Handles audio processing tasks with enhanced validation."""
    
    async def combine_audio_files(
        self, 
        audio_files: List[Path], 
        output_file: Path,
        crossfade_duration: float = 0.5,
        debug: bool = False
    ) -> Path:
        """Combines audio files with validation and debugging."""
        try:
            if not audio_files:
                raise ValueError("No audio files provided")
            
            # Validate input files with duration checks
            valid_files = []
            total_duration = 0
            
            for file in audio_files:
                if not file.exists():
                    logger.warning(f"Audio file does not exist: {file}")
                    continue
                    
                if file.stat().st_size == 0:
                    logger.warning(f"Audio file is empty: {file}")
                    continue
                
                duration = get_audio_duration(file)
                if duration is None or duration < 0.1:  # Less than 100ms
                    logger.warning(f"Invalid audio duration for {file}: {duration}s")
                    continue
                
                if debug:
                    logger.info(f"Valid audio file: {file} (duration: {duration:.2f}s)")
                total_duration += duration
                valid_files.append(file)
            
            if not valid_files:
                raise ValueError("No valid audio files found")
            
            if debug:
                logger.info(f"Total input duration: {total_duration:.2f}s")
            
            if len(valid_files) == 1:
                # Single file - just copy it
                import shutil
                shutil.copy2(valid_files[0], output_file)
                return output_file
            
            # Create ffmpeg filter graph
            filter_parts = []
            inputs = [f'[{i}:a]' for i in range(len(valid_files))]
            
            current_input = inputs[0]
            for i in range(len(valid_files) - 1):
                next_input = inputs[i + 1]
                output_label = f'[a{i}]'
                if i == len(valid_files) - 2:
                    output_label = '[aout]'
                filter_parts.append(
                    f'{current_input}{next_input}acrossfade=d={crossfade_duration}{output_label}'
                )
                current_input = output_label
            
            filter_complex = ';'.join(filter_parts)
            
            # Build and execute ffmpeg command
            cmd = ['ffmpeg', '-y', '-loglevel'] + (['info'] if debug else ['error'])
            
            for audio_file in valid_files:
                cmd.extend(['-i', str(audio_file)])
            
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[aout]',
                str(output_file)
            ])
            
            if debug:
                logger.info(f"FFmpeg command: {' '.join(cmd)}")
            
            # Run ffmpeg
            process = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True)
            )
            
            # Validate output
            if not output_file.exists():
                raise RuntimeError("Output file was not created")
            
            output_duration = get_audio_duration(output_file)
            if output_duration is None or output_duration < 1.0:  # Less than 1 second
                raise RuntimeError(f"Invalid output duration: {output_duration}s")
            
            if debug:
                logger.info(f"Successfully created output file: {output_file}")
                logger.info(f"Output duration: {output_duration:.2f}s")
            
            return output_file
            
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            if isinstance(e, subprocess.CalledProcessError) and e.stderr:
                logger.error(f"FFmpeg error output: {e.stderr}")
            raise

