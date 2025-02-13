"""Main CLI application module."""

import typer
from pathlib import Path
from typing import Optional, Set, Dict
from rich.console import Console
from rich.prompt import Prompt, Confirm
import readline
import os
import glob
import asyncio
import logging
from datetime import datetime

from ..help import CommandHelp
from ..storage import DocumentStore, handle_doc_command
from ..storage.json_storage import JSONStorage
from ..storage.conversation import ConversationStore
from .conversation_commands import (
    handle_add_conversation,
    handle_list_conversations,
    handle_remove_conversation,
    handle_remove_all_conversations,
    handle_remove_all_sources,
    play_conversation,
    show_conversation
)
from .cli_utils import setup_completion  # Updated import
from .. import config
from ..services.podcast_generator import PodcastGenerator
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService
from ..services.audio import AudioProcessor

app = typer.Typer()
console = Console()
logger = logging.getLogger(__name__)

class AsyncApp:
    """Handles async CLI operations."""
    
    def __init__(self):
        # Initialize storage
        data_dir = Path(config.settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        self.storage = JSONStorage(data_dir)
        self.doc_store = DocumentStore(data_dir / "documents.db")
        self.conv_store = ConversationStore(data_dir / "conversations.db")
        self.help_system = CommandHelp()

        # Initialize podcast generation services
        self.content_analyzer = ContentAnalyzer(self.doc_store)
        self.conversation_gen = ConversationGenerator()
        self.tts_service = TTSService()
        self.audio_processor = AudioProcessor()

        self.podcast_generator = PodcastGenerator(
            self.doc_store,
            self.content_analyzer,
            self.conversation_gen,
            self.tts_service,
            self.audio_processor
        )

        # Set up command completion
        setup_completion()

        self.loop = None
        self.background_tasks: Set[asyncio.Task] = set()
        self.conversation_tasks: Dict[int, asyncio.Task] = {}

    def get_event_loop(self):
        """Get or create event loop."""
        if self.loop is None:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
        return self.loop
    
    def _cleanup_background_tasks(self):
        """Clean up completed background tasks."""
        done_tasks = {task for task in self.background_tasks if task.done()}
        self.background_tasks -= done_tasks
        for task in done_tasks:
            try:
                task.result()  # Get result to handle any exceptions
            except Exception as e:
                logger.error(f"Background task failed: {e}")

    async def handle_command(self, cmd: str) -> bool:
        """
        Handle CLI commands starting with /
        Returns False to exit the CLI, True to continue
        """
        try:
            # Clean up completed background tasks
            self._cleanup_background_tasks()
            
            parts = cmd[1:].split()
            if not parts:
                return True
                
            command = parts[0]
            args = parts[1:]
            
            if command == "add":
                if not args:
                    console.print("[red]Missing command argument: source or conversation")
                    return True
                    
                subcmd = args[0]
                if subcmd == "source":
                    if len(args) < 2:
                        console.print("[red]Missing source path or URL")
                        return True
                    await handle_doc_command(f"/add {' '.join(args[1:])}", self.doc_store, console)
                elif subcmd == "conversation":
                    # Check for debug mode
                    debug_mode = len(args) > 1 and args[1] == "debug"
                    task = await handle_add_conversation(
                        console,
                        self.conv_store,
                        self.doc_store,
                        self.podcast_generator,
                        Path(config.settings.output_dir),
                        debug=debug_mode
                    )
                    if task:
                        self.background_tasks.add(task)
                        # Store task with conversation ID
                        self.conversation_tasks[task.conversation_id] = task
                        # Task cleanup callbacks
                        task.add_done_callback(lambda t: self.background_tasks.discard(t))
                        task.add_done_callback(lambda t: self.conversation_tasks.pop(getattr(t, 'conversation_id', None), None))
                else:
                    console.print(f"[red]Unknown add command: {subcmd}")
                    
            elif command == "list":
                if not args:
                    console.print("[red]Missing command argument: sources or conversations")
                    return True
                    
                subcmd = args[0]
                if subcmd == "sources":
                    await handle_doc_command("/list", self.doc_store, console)
                elif subcmd == "conversations":
                    handle_list_conversations(console, self.conv_store)
                else:
                    console.print(f"[red]Unknown list command: {subcmd}")
                    
            elif command == "remove":
                if len(args) < 1:
                    console.print("[red]Missing command arguments")
                    console.print("Usage: /remove <all|conversation|source> [id]")
                    return True
                
                subcmd = args[0]
                if subcmd == "all":
                    if len(args) < 2:
                        console.print("[red]Missing target for bulk removal")
                        console.print("Usage: /remove all <conversations|sources>")
                        return True
                        
                    target = args[1].lower()
                    if target in ["conversations", "conversation"]:
                        await handle_remove_all_conversations(console, self.conv_store, self.conversation_tasks)
                    elif target in ["sources", "source"]:
                        handle_remove_all_sources(console, self.doc_store)
                    else:
                        console.print(f"[red]Unknown target for bulk removal: {target}")
                        console.print("Usage: /remove all <conversations|sources>")
                        
                elif subcmd == "source":
                    if len(args) < 2:
                        console.print("[red]Missing source ID")
                        return True
                    await handle_doc_command(f"/remove {args[1]}", self.doc_store, console)
                elif subcmd == "conversation":
                    if len(args) < 2:
                        console.print("[red]Missing conversation ID")
                        return True
                    try:
                        conv_id = int(args[1])
                        await handle_remove_conversation(console, self.conv_store, conv_id, self.conversation_tasks)
                    except ValueError:
                        console.print("[red]Invalid conversation ID")
                else:
                    console.print("[red]Unknown remove command or missing arguments")
                    console.print("Usage: /remove <all|conversation|source> [id]")
                   
            elif command == "play":
                if not args or args[0] != "conversation" or len(args) != 2:
                    console.print("[red]Usage: /play conversation <id>")
                    return True
                    
                try:
                    conv_id = int(args[1])
                    await play_conversation(console, self.conv_store, conv_id)
                except ValueError:
                    console.print("[red]Invalid conversation ID")
                    
            elif command == "show":
                if not args or args[0] != "conversation" or len(args) != 2:
                    console.print("[red]Usage: /show conversation <id>")
                    return True
                    
                try:
                    conv_id = int(args[1])
                    show_conversation(console, self.conv_store, conv_id)
                except ValueError:
                    console.print("[red]Invalid conversation ID")
                    
            elif command == "help":
                if len(args) > 0:
                    self.help_system.show_help(console, category=args[0])
                else:
                    self.help_system.show_help(console)
                    
            elif command == "bye":
                # Check if there are any active background tasks
                active_tasks = {t for t in self.background_tasks if not t.done()}
                if active_tasks:
                    if Confirm.ask("[yellow]There are background tasks running. Wait for them to complete?"):
                        console.print("[yellow]Waiting for background tasks to complete...")
                        await asyncio.gather(*active_tasks)
                    else:
                        console.print("[yellow]Cancelling background tasks...")
                        for task in active_tasks:
                            task.cancel()
                            
                console.print("Goodbye!")
                return False
                    
            else:
                console.print(f"[red]Unknown command: {command}")
                console.print("Use /help to see available commands")
            
            return True
            
        except Exception as e:
            logger.error(f"Command error: {e}")
            console.print(f"[red]Error executing command: {str(e)}")
            return True
    
    async def run_interactive(self, input_text: Optional[str] = None):
        """Run interactive CLI session."""
        try:
            # Store input text from command line
            current_text = input_text
            
            while True:
                try:
                    # Clean up completed background tasks
                    self._cleanup_background_tasks()
                    
                    # Get input text
                    if current_text:
                        text_to_process = current_text
                        current_text = None  # Clear for next iteration
                    else:
                        try:
                            text_to_process = Prompt.ask("\npodgen")
                        except EOFError:  # Handle Ctrl+D
                            console.print("\nGoodbye!")
                            break
                            
                    if text_to_process.startswith("/"):
                        should_continue = await self.handle_command(text_to_process)
                        if not should_continue:
                            break
                        continue
                        
                    if not text_to_process:
                        continue
                    
                    # Process the text...
                    
                except KeyboardInterrupt:  # Handle Ctrl+C
                    console.print("\nOperation cancelled")
                    continue
                
                if input_text:  # If we started with command line text, exit
                    break
        
        except Exception as e:
            console.print(f"[red]Error: {str(e)}")
            raise typer.Exit(1)
        finally:
            # Cancel any remaining background tasks
            for task in self.background_tasks:
                if not task.done():
                    task.cancel()
            
            # Clean up event loop
            if self.loop and not self.loop.is_running():
                try:
                    # Only close if loop is not running
                    pending = asyncio.all_tasks(self.loop)
                    if not pending:
                        self.loop.close()
                except Exception as e:
                    logger.debug(f"Loop cleanup error: {e}")  # Not critical

@app.command()
def main(
    input_text: Optional[str] = typer.Argument(None, help="Input text (optional)"),
    format: Optional[str] = typer.Option(None, help="Named conversation format"),
    output_dir: Path = typer.Option(
        Path("output"),
        help="Directory for output files"
    ),
):
    """Interactive podcast generator."""
    # Initialize async app
    async_app = AsyncApp()
    
    try:
        # Get event loop
        loop = async_app.get_event_loop()
        
        # Run interactive session
        loop.run_until_complete(async_app.run_interactive(input_text))
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}")
        raise typer.Exit(1)
    finally:
        # Let the loop complete any remaining tasks
        try:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Run loop one more time to let tasks clean up
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.debug(f"Cleanup error: {e}")  # Not critical

if __name__ == "__main__":
    app()

