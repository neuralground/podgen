"""Command registry initialization and management."""

import logging
from typing import Dict, Optional
from rich.console import Console

from ..command_registry import CommandRegistry
from .path_commands import register_commands as register_path_commands
from .key_commands import register_commands as register_key_commands
from .doc_commands import register_commands as register_doc_commands
from .podcast_commands import register_commands as register_podcast_commands

logger = logging.getLogger(__name__)

# Global command registry
registry = CommandRegistry()

def initialize_commands() -> CommandRegistry:
    """Initialize and register all commands."""
    try:
        # Register commands from each module
        register_path_commands(registry)
        register_key_commands(registry)
        register_doc_commands(registry)
        register_podcast_commands(registry)
        
        # Register built-in help command
        registry.register(
            "help", 
            registry.show_help,
            "Show help information"
        )
        
        # Register built-in exit/quit commands
        registry.register(
            "exit", 
            lambda console, args: "EXIT",
            "Exit the application"
        )
        
        registry.register(
            "quit", 
            lambda console, args: "EXIT",
            "Quit the application"
        )
        
        registry.register(
            "bye", 
            lambda console, args: "EXIT",
            "Exit the application"
        )
        
        logger.info(f"Initialized command registry with {len(registry.commands)} commands")
        return registry
        
    except Exception as e:
        logger.error(f"Error initializing commands: {e}")
        # Create a minimal registry with just help and exit
        emergency_registry = CommandRegistry()
        emergency_registry.register("help", emergency_registry.show_help, "Show help information")
        emergency_registry.register("exit", lambda console, args: "EXIT", "Exit the application")
        return emergency_registry

async def execute_command(console: Console, command_text: str) -> Optional[str]:
    """Execute a command and return result."""
    if not command_text.startswith('/'):
        return None
        
    # Execute the command
    return await registry.execute(console, command_text)

# Initialize the registry when module is imported
registry = initialize_commands()
