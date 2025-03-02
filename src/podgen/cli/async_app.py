"""Async application handler for podgen CLI."""

import asyncio
import logging
from typing import Dict, List, Optional, Set
from pathlib import Path
import traceback

from rich.console import Console
from rich.prompt import Prompt

from ..config import settings
from ..storage.document_store import DocumentStore
from ..storage.conversation import ConversationStore
from ..storage.json_storage import JSONStorage
from ..services.podcast_generator import PodcastGenerator
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService, TTSProvider, create_engine
from ..services.audio import AudioProcessor
from ..services.llm import LLMProvider
from .model_config import ModelConfig
from .commands import execute_command

logger = logging.getLogger(__name__)

class AsyncApp:
    """Handles asynchronous CLI operations."""
    
    def __init__(self, model_config: ModelConfig, console: Optional[Console] = None):
        """Initialize the app with configuration."""
        self.model_config = model_config
        self.console = console or Console()
        self.debug = False
        
        # Initialize services
        self._initialize_services()
        
        # Set up async task tracking
        self.background_tasks: Set[asyncio.Task] = set()
        self.conversation_tasks: Dict[int, asyncio.Task] = {}
        
        logger.info("AsyncApp initialization complete")
    
    def _initialize_services(self) -> None:
        """Initialize all services."""
        try:
            logger.info("Initializing services...")
            
            # Use path manager
            self.paths = settings.paths
            
            # Initialize storage with standard locations
            self.storage = JSONStorage(self.paths.get_path("data"))
            self.doc_store = DocumentStore(self.paths.get_db_path("documents"))
            self.conv_store = ConversationStore(self.paths.get_db_path("conversations"))
            
            # Get API keys
            api_keys = self._get_api_keys()
            
            # Create content analyzer
            self.content_analyzer = ContentAnalyzer(
                self.doc_store,
                llm_provider=self.model_config.llm_provider,
                llm_model=self.model_config.llm_model,
                api_key=api_keys.get("openai")
            )
            
            # Create conversation generator
            self.conversation_gen = ConversationGenerator(
                llm_provider=self.model_config.llm_provider,
                llm_model=self.model_config.llm_model,
                api_key=api_keys.get("openai")
            )
            
            # Create TTS service
            self.tts_service = TTSService()
            
            # Create TTS engine if needed
            if self.model_config.tts_type != TTSProvider.SYSTEM:
                tts_engine = create_engine(
                    provider=self.model_config.tts_provider,
                    model_name=self.model_config.tts_model,
                    api_key=self._get_tts_api_key()
                )
                if tts_engine:
                    self.tts_service.add_engine(tts_engine, default=True)
            
            # Create audio processor
            self.audio_processor = AudioProcessor()
            
            # Create podcast generator
            self.podcast_generator = PodcastGenerator(
                self.doc_store,
                self.content_analyzer,
                self.conversation_gen,
                self.tts_service,
                self.audio_processor
            )
            
            logger.info("Services initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            if self.debug:
                logger.error(traceback.format_exc())
            raise RuntimeError(f"Failed to initialize services: {e}")
    
    def _get_api_keys(self) -> Dict[str, str]:
        """Get API keys based on configuration."""
        api_keys = {}
        
        # Get OpenAI API key if needed
        if self.model_config.llm_type == LLMProvider.OPENAI or self.model_config.tts_type == TTSProvider.OPENAI:
            api_key = settings.get_openai_api_key(prompt_if_missing=True)
            if api_key:
                api_keys["openai"] = api_key
            else:
                self.console.print("[yellow]Warning: OpenAI API key not found. Some features may be unavailable.")
        
        # Get ElevenLabs API key if needed
        if self.model_config.tts_type == TTSProvider.ELEVENLABS:
            api_key = settings.get_elevenlabs_api_key(prompt_if_missing=True)
            if api_key:
                api_keys["elevenlabs"] = api_key
            else:
                self.console.print("[yellow]Warning: ElevenLabs API key not found. Some features may be unavailable.")
        
        return api_keys
    
    def _get_tts_api_key(self) -> Optional[str]:
        """Get TTS API key based on provider."""
        if self.model_config.tts_type == TTSProvider.OPENAI:
            return settings.get_openai_api_key()
        elif self.model_config.tts_type == TTSProvider.ELEVENLABS:
            return settings.get_elevenlabs_api_key()
        return None
    
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
            
    def _print_welcome(self) -> None:
        """Print welcome message and configuration."""
        self.console.print("[bold green]Podgen - AI Podcast Generator[/bold green]")
        self.console.print(f"[green]Using configuration directory: {settings.podgen_dir}[/green]")
        self.console.print(f"[green]Output files will be saved to: {self.model_config.output_dir}[/green]")
        self.console.print()
        
        self.console.print("[green]Active Model Configuration:[/green]")
        self.console.print(f"LLM: {self.model_config.llm_type} ({self.model_config.llm_model})")
        self.console.print(f"TTS: {self.model_config.tts_type}", end="")
        if self.model_config.tts_model:
            self.console.print(f" ({self.model_config.tts_model})")
        self.console.print()
        
        # Show some basic commands
        self.console.print("[green]Quick Start:[/green]")
        self.console.print("  /add source <file>       - Add a document")
        self.console.print("  /add conversation        - Generate a podcast")
        self.console.print("  /help                    - Show all commands")
        self.console.print()
    
    async def run_interactive(self, input_text: Optional[str] = None) -> None:
        """Run interactive CLI session."""
        try:
            # Print welcome message
            self._print_welcome()
            
            # Store initial input text
            current_text = input_text
            
            # Main command loop
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
                            text_to_process = Prompt.ask("podgen")
                        except EOFError:  # Handle Ctrl+D
                            self.console.print("\nGoodbye!")
                            break
                    
                    # Process input
                    if text_to_process.startswith('/'):
                        # Execute command
                        result = await execute_command(self.console, text_to_process)
                        
                        # Check if exit command
                        if result == "EXIT":
                            self.console.print("Goodbye!")
                            break
                    else:
                        # Non-command input (for future expansion)
                        self.console.print("[yellow]Please enter a command starting with '/'")
                        self.console.print("Use /help to see available commands")
                        
                except KeyboardInterrupt:  # Handle Ctrl+C
                    self.console.print("\nOperation cancelled")
                    continue
                except Exception as e:
                    logger.error(f"Error processing input: {e}")
                    self.console.print(f"[red]Error: {str(e)}")
                    if self.debug:
                        self.console.print_exception()
                    continue
                    
        except Exception as e:
            logger.error(f"Error in interactive session: {e}")
            self.console.print(f"[red]Error: {str(e)}")
            if self.debug:
                self.console.print_exception()
                