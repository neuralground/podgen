"""Command registry initialization and management."""

import logging
from typing import Dict, Optional
from rich.console import Console
from pathlib import Path
import asyncio
import traceback

from ..command_registry import CommandRegistry
from .path_commands import register_commands as register_path_commands
from .key_commands import register_commands as register_key_commands
from .doc_commands import register_commands as register_doc_commands
from .podcast_commands import register_commands as register_podcast_commands

logger = logging.getLogger(__name__)

# Global command registry
registry = CommandRegistry()

def initialize_commands(podcast_gen=None) -> CommandRegistry:
    """Initialize and register all commands."""
    try:
        # Register commands from each module
        register_path_commands(registry)
        register_key_commands(registry)
        register_doc_commands(registry)
        register_podcast_commands(registry, podcast_gen)
        
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
    logger.debug(f"execute_command called with: {command_text}")
    if not command_text.startswith('/'):
        return None
        
    logger.debug(f"Attempting to execute command: {command_text}")
    
    try:
        # Parse command
        parts = command_text[1:].split()
        if not parts:
            return None
        
        command = parts[0].lower()
        args = parts[1:]
        
        # Special handling for document commands
        if command == "add" and len(args) > 0 and args[0] == "source":
            logger.debug("Direct handling for /add source")
            from ...storage.document_cli import handle_doc_command
            from ...storage.document_store import DocumentStore
            
            # Create document store and handle command
            doc_store = DocumentStore(Path.home() / ".podgen/data/documents.db")
            await handle_doc_command(command_text, doc_store, console)
            return None
            
        elif command == "list" and len(args) > 0 and args[0] == "sources":
            logger.debug("Direct handling for /list sources")
            from ...storage.document_cli import handle_doc_command
            from ...storage.document_store import DocumentStore
            
            # Create document store and handle command
            doc_store = DocumentStore(Path.home() / ".podgen/data/documents.db")
            await handle_doc_command(command_text, doc_store, console)
            return None
        
        # Standard command execution
        logger.debug(f"Executing via registry: {command} with args {args}")
        result = await registry.execute(console, command_text)
        logger.debug(f"Command result: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error in execute_command: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        console.print(f"[red]Error executing command: {str(e)}")
        return None

# Initialize the registry when module is imported
registry = initialize_commands(None)

# Export registry and execute_command for use by other modules
__all__ = ['registry', 'execute_command']
