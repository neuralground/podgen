"""Main CLI application module."""

import typer
from pathlib import Path
from typing import Optional, Set, Dict
from rich.console import Console
from rich.prompt import Prompt, Confirm
import readline
import os
import logging
from datetime import datetime
from enum import Enum
import asyncio

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
from .cli_utils import setup_completion
from .. import config
from ..services.podcast_generator import PodcastGenerator
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService, TTSProvider, create_engine
from ..services.audio import AudioProcessor
from ..services.llm_service import LLMProvider

# Add CLI options as enums
class LLMType(str, Enum):
    openai = "openai"
    ollama = "ollama"
    llamacpp = "llamacpp"

# Import TTSType from config
TTSType = config.TTSProvider

app = typer.Typer()
console = Console()
logger = logging.getLogger(__name__)

class ModelConfig:
    """Configuration for model selection."""
    def __init__(
        self,
        llm_type: LLMType = LLMType.openai,
        llm_model: str = "gpt-4",
        tts_type: TTSType = TTSType.SYSTEM,
        tts_model: Optional[str] = None,
    ):
        self.llm_type = llm_type
        self.llm_model = llm_model
        self.tts_type = tts_type
        self.tts_model = tts_model

    @property
    def llm_provider(self) -> LLMProvider:
        return LLMProvider(self.llm_type.value)

    @property
    def tts_provider(self) -> TTSProvider:
        return TTSProvider(self.tts_type.value)

class AsyncApp:
    """Handles async CLI operations."""
    
    def __init__(self, model_config: ModelConfig):
        # Store model configuration
        self.model_config = model_config
        
        # Initialize storage
        data_dir = Path(config.settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        self.storage = JSONStorage(data_dir)
        self.doc_store = DocumentStore(data_dir / "documents.db")
        self.conv_store = ConversationStore(data_dir / "conversations.db")
        self.help_system = CommandHelp()

        # Get API key from settings (which loads from .env)
        api_key = config.settings.openai_api_key
        if not api_key and self.model_config.llm_type == LLMType.openai:
            raise ValueError("OPENAI_API_KEY not set in .env file")

        # Initialize services with configured models
        self.content_analyzer = ContentAnalyzer(
            self.doc_store,
            llm_provider=self.model_config.llm_provider,
            llm_model=self.model_config.llm_model,
            api_key=api_key
        )
        
        self.conversation_gen = ConversationGenerator(
            llm_provider=self.model_config.llm_provider,
            llm_model=self.model_config.llm_model,
            api_key=api_key
        )
        
        # Create TTS engine based on configuration
        tts_engine = None
        if self.model_config.tts_type != TTSType.SYSTEM:
            tts_engine = create_engine(
                provider=TTSProvider(self.model_config.tts_type.value),
                model_name=self.model_config.tts_model
            )
        
        # Initialize TTS service with engine
        self.tts_service = TTSService()
        if tts_engine:
            self.tts_service.add_engine(tts_engine, default=True)
        
        self.audio_processor = AudioProcessor()

        self.podcast_generator = PodcastGenerator(
            self.doc_store,
            self.content_analyzer,
            self.conversation_gen,
            self.tts_service,
            self.audio_processor
        )

        # Set up additional properties
        self.loop = None
        self.background_tasks: Set[asyncio.Task] = set()
        self.conversation_tasks: Dict[int, asyncio.Task] = {}

        setup_completion()

    def _cleanup_background_tasks(self) -> None:
        """Clean up completed background tasks."""
        # Remove completed background tasks
        done_tasks = {task for task in self.background_tasks if task.done()}
        self.background_tasks.difference_update(done_tasks)

        # Remove completed conversation tasks
        done_convs = [
            conv_id for conv_id, task in self.conversation_tasks.items()
            if task.done()
        ]
        for conv_id in done_convs:
            del self.conversation_tasks[conv_id]

    async def run_interactive(self, input_text: Optional[str] = None):
        """Run interactive CLI session."""
        try:
            # Log active models
            console.print(f"[green]Active configuration:")
            console.print(f"LLM: {self.model_config.llm_type} ({self.model_config.llm_model})")
            console.print(f"TTS: {self.model_config.tts_type}", end="")
            if self.model_config.tts_model:
                console.print(f" ({self.model_config.tts_model})")
            console.print()
            
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
                            # Use prompt.ask correctly
                            text_to_process = Prompt.ask("podgen")
                        except EOFError:  # Handle Ctrl+D
                            console.print("\nGoodbye!")
                            break
                    
                    # Handle exit commands
                    if text_to_process.lower() in ['/quit', '/exit', '/bye']:
                        console.print("Goodbye!")
                        break
                        
                    # Process commands
                    if text_to_process.startswith('/'):
                        # Handle command (existing command processing code)
                        command = text_to_process[1:].split()
                        if not command:
                            continue
                            
                        cmd = command[0].lower()
                        args = command[1:]
                        
                        # Add your command handling here...
                        
                    else:
                        # Handle text input for conversation
                        # Add your text processing here...
                        pass
                        
                except KeyboardInterrupt:  # Handle Ctrl+C
                    console.print("\nOperation cancelled")
                    continue
                except Exception as e:
                    console.print(f"[red]Error: {str(e)}")
                    if hasattr(self, 'debug') and self.debug:
                        import traceback
                        console.print(traceback.format_exc())
                    continue
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}")
            raise typer.Exit(1)
    
@app.command()
def main(
    input_text: Optional[str] = typer.Argument(None, help="Input text (optional)"),
    format: Optional[str] = typer.Option(None, help="Named conversation format"),
    output_dir: Path = typer.Option(
        Path("output"),
        help="Directory for output files"
    ),
    llm_type: Optional[LLMType] = typer.Option(
        None,
        help="Type of LLM to use (overrides .env setting)"
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        help="Specific LLM model to use (overrides .env setting)"
    ),
    tts_type: Optional[TTSType] = typer.Option(
        None,
        help="Type of TTS to use (overrides .env setting)"
    ),
    tts_model: Optional[str] = typer.Option(
        None,
        help="Specific TTS model to use (overrides .env setting)"
    ),
    debug: bool = typer.Option(
        False,
        help="Enable debug output"
    )
):
    """Interactive podcast generator with model selection."""

    # Use settings from .env as defaults
    settings = config.settings

    # Create model configuration using .env settings if CLI args not provided
    model_config = ModelConfig(
        llm_type=llm_type or LLMType(settings.llm_provider.value),
        llm_model=llm_model or settings.llm_model,
        tts_type=tts_type or TTSType(settings.tts_provider.value),
        tts_model=tts_model or settings.tts_model
    )

    # Initialize async app with model configuration
    async_app = AsyncApp(model_config)

    try:
        # Get event loop
        loop = asyncio.get_event_loop()

        # Run interactive session
        loop.run_until_complete(async_app.run_interactive(input_text))

    except Exception as e:
        console.print(f"[red]Error: {str(e)}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)

if __name__ == "__main__":
    app()

