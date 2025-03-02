import time
import asyncio
import platform
import signal
import sys
import termios
import tty
import select
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

@dataclass
class PlaybackState:
    playing: bool = False
    paused: bool = False
    current_time: float = 0.0
    duration: float = 0.0

class AudioPlayer:
    """Audio player with playback controls."""
    
    def __init__(self, console: Console):
        self.console = console
        self.state = PlaybackState()
        self._process = None
        
    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        try:
            import wave
            with wave.open(str(audio_path), 'rb') as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / float(rate)
        except Exception as e:
            self.console.print(f"[red]Error getting audio duration: {e}")
            return 0.0
            
    def _format_time(self, seconds: float) -> str:
        """Format time as mm:ss."""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    async def play(self, audio_path: Path, title: str = "Now Playing") -> None:
        """Play audio file with controls."""
        if not audio_path.exists():
            self.console.print(f"[red]Audio file not found: {audio_path}")
            return
        
        # Get audio duration
        duration = self._get_audio_duration(audio_path)
        if duration <= 0:
            self.console.print("[red]Invalid audio file duration")
            return
            
        self.state = PlaybackState(
            playing=True,
            duration=duration
        )
        
        # Create player process
        try:
            if platform.system() == "Darwin":  # macOS
                cmd = ["afplay", str(audio_path)]
            elif platform.system() == "Windows":
                cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{audio_path}').PlaySync()"]
            else:  # Linux
                cmd = ["aplay", str(audio_path)]
            
            # Start process
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Prepare keyboard handling
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
            
            try:
                start_time = time.time()
                
                # Print title once
                self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
                self.console.print("\nPress Space to pause/resume, Q to quit\n")
                
                # Create progress bar
                progress = Progress(
                    SpinnerColumn(),
                    BarColumn(complete_style="cyan", finished_style="cyan"),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("{task.description}"),
                    console=self.console,
                    expand=True
                )
                
                with progress:
                    # Add main progress task
                    task_id = progress.add_task(
                        description="0:00 / 0:00",
                        total=float(duration)
                    )
                    
                    while self.state.playing:
                        # Update current time
                        if not self.state.paused:
                            self.state.current_time = min(
                                time.time() - start_time,
                                self.state.duration
                            )
                            
                            # Update progress
                            time_display = f"{self._format_time(self.state.current_time)} / {self._format_time(self.state.duration)}"
                            progress.update(task_id, 
                                         completed=self.state.current_time,
                                         description=time_display)
                        
                        # Check keyboard input
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            key = sys.stdin.read(1)
                            
                            if key == " ":  # Space - Play/Pause
                                self.state.paused = not self.state.paused
                                if self.state.paused:
                                    if platform.system() == "Darwin":
                                        await asyncio.create_subprocess_exec(
                                            "kill", "-STOP", str(self._process.pid)
                                        )
                                    else:
                                        self._process.send_signal(signal.SIGSTOP)
                                else:
                                    if platform.system() == "Darwin":
                                        await asyncio.create_subprocess_exec(
                                            "kill", "-CONT", str(self._process.pid)
                                        )
                                    else:
                                        self._process.send_signal(signal.SIGCONT)
                                    start_time = time.time() - self.state.current_time
                                    
                            elif key.lower() == "q":  # Q - Stop
                                self.state.playing = False
                                break
                        
                        # Check if process has ended
                        if self._process.returncode is not None:
                            self.state.playing = False
                            break
                        
                        await asyncio.sleep(0.1)
                    
                # Add final newline
                self.console.print()
                    
            finally:
                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                
        except Exception as e:
            self.console.print(f"[red]Playback error: {e}")
            
        finally:
            if self._process:
                try:
                    self._process.terminate()
                    await self._process.wait()
                except:
                    pass
                    
            self._process = None
            self.state = PlaybackState()
            