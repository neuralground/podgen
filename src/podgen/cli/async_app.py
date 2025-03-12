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
from ..storage.conversation.store import ConversationStore
from ..storage.json_storage import JSONStorage
from ..services.podcast_generator import PodcastGenerator
from ..services.content_analyzer import ContentAnalyzer
from ..services.conversation import ConversationGenerator
from ..services.tts import TTSService, TTSProvider, create_engine
from ..services.audio import AudioProcessor
from ..services.llm import LLMProvider
from .services.model_config import ModelConfig
from .commands import execute_command, registry
from .commands.podcast_commands import PodcastCommands, register_commands

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
    
    def _initialize_services(self):
        """Initialize all services."""
        try:
            # Set up paths
            self.paths = settings.paths
            
            # Initialize storage with standard locations
            self.storage = JSONStorage(self.paths.get_path("data"))
            
            # Get API keys
            api_keys = self._get_api_keys()
            
            # Create document store
            self.doc_store = DocumentStore(settings.paths.get_db_path("documents"))
            
            # Create conversation store
            self.conv_store = ConversationStore(settings.paths.get_db_path("conversations"))
            
            # Create content analyzer
            self.content_analyzer = ContentAnalyzer(
                doc_store=self.doc_store,
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
                    provider=self.model_config.tts_type,
                    model_name=self.model_config.tts_model,
                    api_key=self._get_tts_api_key()
                )
                if tts_engine:
                    self.tts_service.add_engine(tts_engine, default=True)
            
            # Create audio processor
            self.audio_processor = AudioProcessor()
            
            # Create podcast generator
            self.podcast_gen = PodcastGenerator(
                doc_store=self.doc_store,
                content_analyzer=self.content_analyzer,
                conversation_gen=self.conversation_gen,
                tts_service=self.tts_service,
                audio_processor=self.audio_processor
            )
            
            # Create podcast commands with our services
            self.podcast_commands = PodcastCommands(
                conv_store=self.conv_store,
                doc_store=self.doc_store,
                podcast_gen=self.podcast_gen,
                output_dir=settings.paths.get_path("output")
            )
            
            # Share background tasks with podcast commands
            self.conversation_tasks = self.podcast_commands.conversation_tasks
            
            # Update the command registry with our podcast generator
            from .commands import registry
            if hasattr(registry, 'podcast_commands'):
                # Update the existing podcast commands with our podcast generator
                registry.podcast_commands.podcast_gen = self.podcast_gen
                logger.info("Updated command registry with podcast generator")
            else:
                # Re-initialize the commands with our podcast generator
                from .commands import initialize_commands
                new_registry = initialize_commands(self.podcast_gen)
                
                # Copy all commands from the new registry to the existing one
                for command_name, command in new_registry.commands.items():
                    registry.commands[command_name] = command
                
                for command_name, subcommands in new_registry.subcommands.items():
                    registry.subcommands[command_name] = subcommands
                
                logger.info("Re-initialized command registry with podcast generator")
            
            logger.info("Services initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise
    
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
        # Suppress welcome messages - only log them
        logger.info("Podgen - AI Podcast Generator")
        logger.info(f"Using configuration directory: {settings.podgen_dir}")
        logger.info(f"Output files will be saved to: {self.model_config.output_dir}")
        
        logger.info(f"LLM: {self.model_config.llm_type} ({self.model_config.llm_model})")
        logger.info(f"TTS: {self.model_config.tts_type} {self.model_config.tts_model if self.model_config.tts_model else ''}")
    
    async def run_interactive(self, input_text: Optional[str] = None) -> None:
        """Run interactive CLI session."""
        try:
            # Log welcome message instead of printing it
            self._print_welcome()
            
            # Store initial input text
            current_text = input_text
            
            # Main interaction loop
            while True:
                try:
                    # Process any text we have
                    text_to_process = None
                    
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
                        try:
                            # Execute command
                            result = await execute_command(self.console, text_to_process)
                            
                            # Check if exit command
                            if result == "EXIT":
                                # Wait for any background tasks to complete before exiting
                                if self.conversation_tasks:
                                    self.console.print("[yellow]Waiting for background tasks to complete...")
                                    for task_id, task in list(self.conversation_tasks.items()):
                                        if not task.done():
                                            self.console.print(f"[yellow]Task for conversation {task_id} is still running")
                                
                                self.console.print("Goodbye!")
                                break
                        except Exception as e:
                            logger.error(f"Error executing command: {e}")
                            if self.debug:
                                self.console.print_exception()
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