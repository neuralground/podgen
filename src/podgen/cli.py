import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
import readline
import os
import glob

from .help import CommandHelp
from .storage import DocumentStore, handle_doc_command
from .storage.json_storage import JSONStorage
from . import config

app = typer.Typer()
console = Console()

# Initialize services
storage = JSONStorage(Path(config.settings.data_dir))
doc_store = DocumentStore(Path(config.settings.data_dir) / "documents.db")
help_system = CommandHelp()

class PodgenCompleter:
    """Handles command and file path completion"""
    
    def __init__(self):
        self.commands = {
            "help": None,
            "add": self._complete_path,
            "list": None,
            "remove": None,
            "bye": None,
            "speakers": None,
            "formats": None
        }
        self.current_candidates = []

    def complete(self, text: str, state: int) -> Optional[str]:
        """Main completion method"""
        if state == 0:
            # This is the first time for this text,
            # so build a match list
            line = readline.get_line_buffer()
            begidx = readline.get_begidx()
            endidx = readline.get_endidx()
            
            if begidx == 0:
                # Complete command
                self.current_candidates = [
                    f"/{cmd} " for cmd in self.commands
                    if cmd.startswith(text[1:] if text.startswith('/') else text)
                ]
            else:
                # Complete arguments
                command = line.split()[0][1:]  # Remove leading slash
                if command in self.commands and self.commands[command]:
                    self.current_candidates = self.commands[command](text)
                else:
                    self.current_candidates = []
                    
        try:
            return self.current_candidates[state]
        except IndexError:
            return None

    def _complete_path(self, text: str) -> list[str]:
        """Complete file paths"""
        if not text:
            completions = glob.glob('*')
        else:
            # Expand ~ to home directory
            if text.startswith('~'):
                text = os.path.expanduser(text)
            
            # If text ends with separator, list contents
            if text.endswith(os.sep):
                completions = glob.glob(text + '*')
            else:
                completions = glob.glob(text + '*')
        
        # Add separator to directories
        return [
            f"{c}{os.sep if os.path.isdir(c) else ' '}"
            for c in completions
        ]

def setup_readline():
    """Configure readline with our completer"""
    completer = PodgenCompleter()
    readline.set_completer(completer.complete)
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind('tab: complete')

def handle_command(cmd: str) -> bool:
    """
    Handle CLI commands starting with /
    Returns False to exit the CLI, True to continue
    """
    parts = cmd[1:].split()
    if not parts:
        return True
        
    command = parts[0]
    args = parts[1:]
    
    if command == "help":
        if len(args) > 0:
            help_system.show_help(console, category=args[0] if len(args[0]) > 1 else None, 
                                         command=args[0] if len(args[0]) == 1 else None)
        else:
            help_system.show_help(console)
    elif command == "bye":
        console.print("Goodbye!")
        return False
    elif command in ["add", "list", "remove"]:
        handle_doc_command(cmd, doc_store, console)
    elif command == "speakers":
        # Handler for speaker commands
        handle_speaker_command(cmd, storage, console)
    elif command == "formats":
        # Handler for format commands
        handle_format_command(cmd, storage, console)
    else:
        console.print(f"[red]Unknown command: {command}")
        console.print("Use /help to see available commands")
    
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
        # Initialize services
        setup_readline()
        
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
                    if not handle_command(text_to_process):
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

if __name__ == "__main__":
    app()

