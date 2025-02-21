import time
import asyncio
import platform
import signal
import sys
import termios
import tty
import select
import threading
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from rich.live import Live
from rich.console import Console, Group
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich.align import Align

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
        self._monitor_thread = None
        self._stop_monitor = threading.Event()
        
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
    
    async def play(self, audio_path: Path) -> None:
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
            
            # Enter alternate screen
            with self.console.screen():
                # Initialize progress
                progress = Progress(
                    TextColumn("[bright_cyan]{task.description}"),
                    BarColumn(bar_width=40, complete_style="cyan"),
                    TextColumn("{task.percentage:>3.0f}%"),
                    TextColumn("[bright_cyan]{task.fields[current_time]} / {task.fields[total_time]}"),
                    expand=True,
                    refresh_per_second=10
                )
                
                task_id = progress.add_task(
                    "Playing",
                    total=100,
                    completed=0,
                    current_time="00:00",
                    total_time=self._format_time(self.state.duration)
                )
                
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
                    
                    with progress:
                        while self.state.playing:
                            # Update progress if playing
                            if not self.state.paused:
                                self.state.current_time = min(
                                    time.time() - start_time,
                                    self.state.duration
                                )
                                progress.update(
                                    task_id,
                                    completed=int((self.state.current_time / self.state.duration) * 100),
                                    current_time=self._format_time(self.state.current_time)
                                )
                            
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
                                        progress.update(task_id, description="Paused")
                                    else:
                                        if platform.system() == "Darwin":
                                            await asyncio.create_subprocess_exec(
                                                "kill", "-CONT", str(self._process.pid)
                                            )
                                        else:
                                            self._process.send_signal(signal.SIGCONT)
                                        progress.update(task_id, description="Playing")
                                        start_time = time.time() - self.state.current_time
                                        
                                elif key.lower() == "q":  # Q - Stop
                                    self.state.playing = False
                                    break
                            
                            # Check if process has ended
                            if self._process.returncode is not None:
                                self.state.playing = False
                                break
                            
                            # Add controls display
                            self.console.print("\n")
                            controls = Text()
                            if self.state.paused:
                                controls.append("▶️ ", style="bright_green")
                            else:
                                controls.append("⏸️ ", style="bright_yellow")
                            controls.append("⏹️ ", style="bright_red")
                            self.console.print(Align.center(controls))
                            self.console.print(Align.center(
                                Text("Space: Play/Pause  Q: Stop", style="bright_white")
                            ))
                            
                            await asyncio.sleep(0.1)
                            
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
