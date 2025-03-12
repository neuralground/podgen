"""Main CLI application entry point."""

import typer
import asyncio
import os
import logging
from pathlib import Path
from typing import Optional
import importlib

from rich.console import Console
from rich.prompt import Confirm

from .. import config
from .services.model_config import ModelConfig, LLMType
from .async_app import AsyncApp

# Create Typer app
app = typer.Typer()
console = Console()

# Get logger
logger = logging.getLogger(__name__)

@app.command()
def main(
    input_text: Optional[str] = typer.Argument(None, help="Input text (optional)"),
    format: Optional[str] = typer.Option(None, help="Named conversation format"),
    output_dir: Optional[Path] = typer.Option(
        None,
        help="Directory for output files (overrides default location)"
    ),
    llm_type: Optional[LLMType] = typer.Option(
        None,
        help="Type of LLM to use (overrides .env setting)"
    ),
    llm_model: Optional[str] = typer.Option(
        None,
        help="Specific LLM model to use (overrides .env setting)"
    ),
    tts_type: Optional[config.TTSProvider] = typer.Option(
        None,
        help="Type of TTS to use (overrides .env setting)"
    ),
    tts_model: Optional[str] = typer.Option(
        None,
        help="Specific TTS model to use (overrides .env setting)"
    ),
    data_dir: Optional[Path] = typer.Option(
        None,
        help="Base directory for all data (overrides PODGEN_DIR env variable)"
    ),
    config_name: Optional[str] = typer.Option(
        None,
        help="Load a saved configuration profile"
    ),
    save_config: Optional[str] = typer.Option(
        None,
        help="Save current configuration to a named profile"
    ),
    debug: bool = typer.Option(
        False,
        help="Enable debug output"
    ),
    setup_keys: bool = typer.Option(
        False,
        help="Run interactive API key setup before starting"
    )
):
    """Interactive podcast generator with model selection."""
    try:
        # Configure logging based on debug flag
        log_level = "DEBUG" if debug else config.settings.log_level
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=config.settings.log_file
        )
        
        # Override base directory if specified
        if data_dir:
            os.environ["PODGEN_DIR"] = str(data_dir)
            # Reload settings with new path
            importlib.reload(config)
            logger.info(f"Using custom data directory: {data_dir}")

        # Initialize API keys if requested
        if setup_keys:
            console.print("[bold]API Key Setup[/bold]")
            
            # Initialize OpenAI key
            console.print("\n[bold]OpenAI API Key[/bold]")
            openai_key = config.settings.get_openai_api_key()
            if openai_key:
                console.print("OpenAI API key is already configured.")
                if Confirm.ask("Do you want to replace it?"):
                    config.SecureKeyManager.prompt_for_key("openai-api", force_input=True)
            else:
                config.SecureKeyManager.prompt_for_key("openai-api")
            
            # Initialize ElevenLabs key
            console.print("\n[bold]ElevenLabs API Key[/bold]")
            elevenlabs_key = config.settings.get_elevenlabs_api_key()
            if elevenlabs_key:
                console.print("ElevenLabs API key is already configured.")
                if Confirm.ask("Do you want to replace it?"):
                    config.SecureKeyManager.prompt_for_key("elevenlabs-api", force_input=True)
            else:
                config.SecureKeyManager.prompt_for_key("elevenlabs-api")
            
            console.print("\n[green]API key setup complete![/green]")

        # Get model configuration
        model_config = None
        
        # Check if loading saved config
        if config_name:
            model_config = ModelConfig.load_from_file(config_name)
            if not model_config:
                console.print(f"[yellow]Warning: Could not load configuration '{config_name}'. Using defaults.")
        
        # Create new configuration if not loaded
        if not model_config:
            # Get default TTS settings from environment if not specified
            if tts_type is None:
                env_tts_type = config.settings.tts_provider
                tts_type = env_tts_type if env_tts_type else None
                logger.info(f"Using TTS provider from environment: {tts_type}")
            
            if tts_model is None:
                env_tts_model = config.settings.tts_model
                tts_model = env_tts_model if env_tts_model else None
                logger.info(f"Using TTS model from environment: {tts_model}")
                
            # Default to ElevenLabs if not specified
            if tts_type is None:
                tts_type = config.TTSProvider.ELEVENLABS
                logger.info(f"Defaulting to ElevenLabs TTS provider")
                
            if tts_model is None and tts_type == config.TTSProvider.ELEVENLABS:
                tts_model = "eleven_monolingual_v1"
                logger.info(f"Defaulting to eleven_monolingual_v1 model")
            
            model_config = ModelConfig(
                llm_type=llm_type,
                llm_model=llm_model,
                tts_type=tts_type,
                tts_model=tts_model,
                output_dir=output_dir
            )
        
        # Save configuration if requested
        if save_config:
            config_path = model_config.save_to_file(save_config)
            if config_path:
                console.print(f"[green]Saved configuration as '{save_config}'")
            else:
                console.print("[red]Failed to save configuration")

        # Initialize async application
        async_app = AsyncApp(model_config, console)
        async_app.debug = debug

        # Run the event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_app.run_interactive(input_text))

    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user")
        return
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}")
        if debug:
            console.print_exception()
        raise typer.Exit(1)

if __name__ == "__main__":
    app()