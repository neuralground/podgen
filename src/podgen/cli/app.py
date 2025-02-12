import typer
from pathlib import Path
from typing import Optional
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
    play_conversation,
    show_conversation
)
from .. import config
from ..services.podcast_generator import PodcastGenerator
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService
from ..services.audio import AudioProcessor

app = typer.Typer()
console = Console()

# Initialize services
storage = JSONStorage(Path(config.settings.data_dir))
doc_store = DocumentStore(Path(config.settings.data_dir) / "documents.db")
conv_store = ConversationStore(Path(config.settings.data_dir) / "conversations.db")
help_system = CommandHelp()

# Initialize podcast generation services
content_analyzer = ContentAnalyzer(doc_store)
conversation_gen = ConversationGenerator()
tts_service = TTSService()
audio_processor = AudioProcessor()

podcast_generator = PodcastGenerator(
    doc_store,
    content_analyzer,
    conversation_gen,
    tts_service,
    audio_processor
)

class AsyncCommandHandler:
    """Handles asynchronous command execution."""
    
    def __init__(self):
        self.loop = None
    
    def get_event_loop(self):
        """Get or create event loop."""
        if self.loop is None:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
        return self.loop
    
    def run_async(self, coro):
        """Run coroutine in event loop."""
        loop = self.get_event_loop()
        return loop.run_until_complete(coro)

async def async_handle_command(cmd: str) -> bool:
    """
    Handle CLI commands starting with /
    Returns False to exit the CLI, True to continue
    """
    parts = cmd[1:].split()
    if not parts:
        return True
        
    command = parts[0]
    args = parts[1:]
    
    try:
        if command == "add":
            if not args:
                console.print("[red]Missing command argument: source or conversation")
                return True
                
            subcmd = args[0]
            if subcmd == "source":
                if len(args) < 2:
                    console.print("[red]Missing source path or URL")
                    return True
                handle_doc_command(f"/add {' '.join(args[1:])}", doc_store, console)
            elif subcmd == "conversation":
                await handle_add_conversation(
                    console,
                    conv_store,
                    doc_store,
                    podcast_generator,
                    Path(config.settings.output_dir)
                )
            else:
                console.print(f"[red]Unknown add command: {subcmd}")
                
        elif command == "list":
            if not args:
                console.print("[red]Missing command argument: sources or conversations")
                return True
                
            subcmd = args[0]
            if subcmd == "sources":
                handle_doc_command("/list", doc_store, console)
            elif subcmd == "conversations":
                handle_list_conversations(console, conv_store)
            else:
                console.print(f"[red]Unknown list command: {subcmd}")
                
        elif command == "remove":
            if len(args) < 2:
                console.print("[red]Missing command arguments")
                return True
                
            subcmd = args[0]
            if subcmd == "source":
                handle_doc_command(f"/remove {args[1]}", doc_store, console)
            elif subcmd == "conversation":
                try:
                    conv_id = int(args[1])
                    handle_remove_conversation(console, conv_store, conv_id)
                except ValueError:
                    console.print("[red]Invalid conversation ID")
            else:
                console.print(f"[red]Unknown remove command: {subcmd}")
                
        elif command == "play":
            if not args or args[0] != "conversation" or len(args) != 2:
                console.print("[red]Usage: /play conversation <id>")
                return True
                
            try:
                conv_id = int(args[1])
                play_conversation(console, conv_store, conv_id)
            except ValueError:
                console.print("[red]Invalid conversation ID")
                
        elif command == "show":
            if not args or args[0] != "conversation" or len(args) != 2:
                console.print("[red]Usage: /show conversation <id>")
                return True
                
            try:
                conv_id = int(args[1])
                show_conversation(console, conv_store, conv_id)
            except ValueError:
                console.print("[red]Invalid conversation ID")
                
        elif command == "help":
            if len(args) > 0:
                help_system.show_help(console, category=args[0])
            else:
                help_system.show_help(console)
                
        elif command == "bye":
            console.print("Goodbye!")
            return False
            
        else:
            console.print(f"[red]Unknown command: {command}")
            console.print("Use /help to see available commands")
        
    except Exception as e:
        logger.error(f"Command error: {e}")
        console.print(f"[red]Error executing command: {str(e)}")
    
    return True

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
    try:
        # Initialize command handler
        cmd_handler = AsyncCommandHandler()
        
        # Store input text from command line
        current_text = input_text
        
        while True:
            try:
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
                    # Handle command asynchronously
                    should_continue = cmd_handler.run_async(
                        async_handle_command(text_to_process)
                    )
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
        # Clean up event loop
        if cmd_handler and cmd_handler.loop:
            cmd_handler.loop.close()

if __name__ == "__main__":
    app()

