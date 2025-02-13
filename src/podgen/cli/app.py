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
from ..services.tts import TTSService
from ..services.audio import AudioProcessor
from ..services.llm_service import LLMProvider
from ..services.tts import TTSProvider

# Add CLI options as enums
class ModelType(str, Enum):
    local = "local"
    cloud = "cloud"
    system = "system"

class LLMType(str, Enum):
    openai = "openai"
    ollama = "ollama"
    llamacpp = "llamacpp"

class TTSType(str, Enum):
    openai = "openai"
    elevenlabs = "elevenlabs"
    coqui = "coqui"
    bark = "bark"
    system = "system"

app = typer.Typer()
console = Console()
logger = logging.getLogger(__name__)

class ModelConfig:
    """Configuration for model selection."""
    def __init__(
        self,
        llm_type: LLMType = LLMType.openai,
        llm_model: str = "gpt-4",
        tts_type: TTSType = TTSType.system,
        tts_model: Optional[str] = None,
    ):
        self.llm_type = llm_type
        self.llm_model = llm_model
        self.tts_type = tts_type
        self.tts_model = tts_model

    @property
    def llm_provider(self) -> LLMProvider:
        return {
            LLMType.openai: LLMProvider.OPENAI,
            LLMType.ollama: LLMProvider.OLLAMA,
            LLMType.llamacpp: LLMProvider.LLAMACPP
        }[self.llm_type]

    @property
    def tts_provider(self) -> TTSProvider:
        return {
            TTSType.openai: TTSProvider.OPENAI,
            TTSType.elevenlabs: TTSProvider.ELEVENLABS,
            TTSType.coqui: TTSProvider.COQUI,
            TTSType.bark: TTSProvider.BARK,
            TTSType.system: TTSProvider.SYSTEM
        }[self.tts_type]

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

        # Initialize services with configured models
        self.content_analyzer = ContentAnalyzer(
            self.doc_store,
            llm_provider=self.model_config.llm_provider,
            llm_model=self.model_config.llm_model
        )
        
        self.conversation_gen = ConversationGenerator(
            llm_provider=self.model_config.llm_provider,
            llm_model=self.model_config.llm_model
        )
        
        self.tts_service = TTSService(
            provider=self.model_config.tts_provider,
            model_name=self.model_config.tts_model
        )
        
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
                            text_to_process = Prompt.ask("\npodgen")
                        except EOFError:  # Handle Ctrl+D
                            console.print("\nGoodbye!")
                            break
                    
                    # Handle commands and text processing...
                    # (Rest of the run_interactive implementation remains the same)
                    
                except KeyboardInterrupt:  # Handle Ctrl+C
                    console.print("\nOperation cancelled")
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
    llm_type: LLMType = typer.Option(
        LLMType.openai,
        help="Type of LLM to use"
    ),
    llm_model: str = typer.Option(
        "gpt-4",
        help="Specific LLM model to use"
    ),
    tts_type: TTSType = typer.Option(
        TTSType.system,
        help="Type of TTS to use"
    ),
    tts_model: Optional[str] = typer.Option(
        None,
        help="Specific TTS model to use"
    ),
    debug: bool = typer.Option(
        False,
        help="Enable debug output"
    )
):
    """Interactive podcast generator with model selection."""
    # Create model configuration
    model_config = ModelConfig(
        llm_type=llm_type,
        llm_model=llm_model,
        tts_type=tts_type,
        tts_model=tts_model
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

