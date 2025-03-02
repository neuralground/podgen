"""API key management commands for the podgen CLI."""

import logging
from typing import List, Optional, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
import getpass
import os

from ...config import SecureKeyManager

logger = logging.getLogger(__name__)

# Define known services and their display info
KEY_SERVICES = {
    "openai": {
        "name": "OpenAI",
        "ref": "openai-api",
        "description": "For GPT models and DALL-E",
        "validation": lambda k: k.startswith("sk-") and len(k) > 20
    },
    "elevenlabs": {
        "name": "ElevenLabs",
        "ref": "elevenlabs-api",
        "description": "For high-quality TTS voices",
        "validation": lambda k: len(k) > 20
    }
}

class KeyCommands:
    """Commands for managing API keys."""
    
    def __init__(self, key_manager=None):
        """Initialize with secure key manager."""
        self.key_manager = key_manager or SecureKeyManager
    
    async def set(self, console: Console, args: List[str]) -> None:
        """Set an API key for a service."""
        try:
            if not args:
                console.print("[red]Please specify a service name")
                self._show_available_services(console)
                return
                
            service = args[0].lower()
            if service not in KEY_SERVICES:
                console.print(f"[red]Unknown service: {service}")
                self._show_available_services(console)
                return
                
            # Get the key reference
            key_ref = KEY_SERVICES[service]["ref"]
            display_name = KEY_SERVICES[service]["name"]
            
            # Check if key already exists
            existing_key = self.key_manager.get_key(key_ref)
            if existing_key:
                console.print(f"[yellow]A key for {display_name} already exists.")
                if not Confirm.ask("Do you want to replace it?"):
                    return
            
            # Prompt for the key
            console.print(f"Enter your {display_name} API key (input will be hidden):")
            key = getpass.getpass()
            
            if not key:
                console.print("[red]No key provided")
                return
                
            # Validate the key format
            validator = KEY_SERVICES[service]["validation"]
            if not validator(key):
                console.print("[yellow]Warning: The key format doesn't appear to be valid.")
                if not Confirm.ask("Do you want to store it anyway?"):
                    return
            
            # Store the key
            if self.key_manager.set_key(key_ref, key):
                console.print(f"[green]Successfully stored {display_name} API key")
            else:
                console.print(f"[red]Failed to store {display_name} API key")
                
        except Exception as e:
            logger.error(f"Error setting API key: {e}")
            console.print(f"[red]Error setting API key: {str(e)}")
    
    async def check(self, console: Console, args: List[str]) -> None:
        """Check API key availability."""
        try:
            # Check specific service if provided
            if args:
                service = args[0].lower()
                if service not in KEY_SERVICES:
                    console.print(f"[red]Unknown service: {service}")
                    self._show_available_services(console)
                    return
                    
                key_ref = KEY_SERVICES[service]["ref"]
                display_name = KEY_SERVICES[service]["name"]
                
                # Check if key exists
                key = self.key_manager.get_key(key_ref)
                if key:
                    # Show masked version
                    masked_key = self._mask_key(key)
                    console.print(f"[green]{display_name} API key is available")
                    console.print(f"Key: {masked_key}")
                else:
                    console.print(f"[red]{display_name} API key is not set")
                    console.print(f"Use '/key set {service}' to configure it")
                
                # Check environment variable as fallback
                env_var = f"{service.upper()}_API_KEY"
                if os.environ.get(env_var):
                    console.print(f"[yellow]Note: {env_var} environment variable is also set")
                    
            # Show status for all services
            else:
                table = Table(title="API Key Status")
                table.add_column("Service", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Source", style="yellow")
                
                for service, info in KEY_SERVICES.items():
                    key_ref = info["ref"]
                    display_name = info["name"]
                    
                    # Check secure storage
                    key = self.key_manager.get_key(key_ref)
                    
                    # Check environment variable
                    env_var = f"{service.upper()}_API_KEY"
                    env_key = os.environ.get(env_var)
                    
                    if key:
                        status = "[green]Available"
                        source = "Secure Storage"
                    elif env_key:
                        status = "[green]Available"
                        source = "Environment Variable"
                    else:
                        status = "[red]Not Set"
                        source = "—"
                    
                    table.add_row(display_name, status, source)
                
                console.print(table)
                
        except Exception as e:
            logger.error(f"Error checking API keys: {e}")
            console.print(f"[red]Error checking API keys: {str(e)}")
    
    async def delete(self, console: Console, args: List[str]) -> None:
        """Delete an API key."""
        try:
            if not args:
                console.print("[red]Please specify a service name")
                self._show_available_services(console)
                return
                
            service = args[0].lower()
            if service not in KEY_SERVICES:
                console.print(f"[red]Unknown service: {service}")
                self._show_available_services(console)
                return
            
            key_ref = KEY_SERVICES[service]["ref"]
            display_name = KEY_SERVICES[service]["name"]
            
            # Check if key exists
            key = self.key_manager.get_key(key_ref)
            if not key:
                console.print(f"[yellow]No {display_name} API key found to delete")
                return
                
            # Confirm deletion
            force = "--force" in args
            if not force:
                if not Confirm.ask(f"Are you sure you want to delete the {display_name} API key?"):
                    console.print("[yellow]Operation cancelled")
                    return
            
            # Delete the key
            if self.key_manager.delete_key(key_ref):
                console.print(f"[green]Successfully deleted {display_name} API key")
            else:
                console.print(f"[red]Failed to delete {display_name} API key")
                
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            console.print(f"[red]Error deleting API key: {str(e)}")
    
    async def import_env(self, console: Console, args: List[str]) -> None:
        """Import API keys from environment variables."""
        try:
            imported = False
            
            for service, info in KEY_SERVICES.items():
                key_ref = info["ref"]
                display_name = info["name"]
                env_var = f"{service.upper()}_API_KEY"
                
                # Check if environment variable exists
                env_key = os.environ.get(env_var)
                if not env_key:
                    continue
                    
                # Check if key already exists in secure storage
                existing_key = self.key_manager.get_key(key_ref)
                if existing_key:
                    # Skip if not forcing overwrite
                    if "--force" not in args:
                        console.print(f"[yellow]Skipping {display_name}: key already exists in secure storage")
                        console.print(f"Use '/key import --force' to overwrite existing keys")
                        continue
                
                # Store the key
                if self.key_manager.set_key(key_ref, env_key):
                    console.print(f"[green]Imported {display_name} API key from environment")
                    imported = True
                else:
                    console.print(f"[red]Failed to import {display_name} API key")
            
            if not imported:
                console.print("[yellow]No API keys found in environment variables")
                
        except Exception as e:
            logger.error(f"Error importing API keys: {e}")
            console.print(f"[red]Error importing API keys: {str(e)}")
    
    async def export_env(self, console: Console, args: List[str]) -> None:
        """Export API keys to environment variables (for the current session)."""
        try:
            exported = False
            
            for service, info in KEY_SERVICES.items():
                key_ref = info["ref"]
                display_name = info["name"]
                env_var = f"{service.upper()}_API_KEY"
                
                # Check if key exists in secure storage
                key = self.key_manager.get_key(key_ref)
                if not key:
                    continue
                
                # Set environment variable
                os.environ[env_var] = key
                console.print(f"[green]Exported {display_name} API key to {env_var}")
                exported = True
                
            if not exported:
                console.print("[yellow]No API keys found in secure storage")
                console.print("Use '/key set <service>' to configure keys")
                
            if exported:
                console.print("\n[yellow]Note: Environment variables are only set for the current session")
                console.print("You may need to run '/key export' again in new sessions")
                
        except Exception as e:
            logger.error(f"Error exporting API keys: {e}")
            console.print(f"[red]Error exporting API keys: {str(e)}")
    
    def _show_available_services(self, console: Console) -> None:
        """Show available services."""
        console.print("\n[bold]Available services:[/bold]")
        for service, info in KEY_SERVICES.items():
            console.print(f"  {service} - {info['description']}")
    
    def _mask_key(self, key: str) -> str:
        """Mask an API key for display."""
        if len(key) <= 8:
            return "****"
        
        return f"{key[:4]}...{key[-4:]}"

def register_commands(registry):
    """Register key commands with the command registry."""
    key_commands = KeyCommands()
    
    # Register main command
    registry.register(
        "key", 
        key_commands.check,
        "Manage API keys"
    )
    
    # Register subcommands
    registry.register_subcommand(
        "key", "set", 
        key_commands.set,
        "Set an API key for a service"
    )
    
    registry.register_subcommand(
        "key", "check", 
        key_commands.check,
        "Check API key availability"
    )
    
    registry.register_subcommand(
        "key", "delete", 
        key_commands.delete,
        "Delete an API key"
    )
    
    registry.register_subcommand(
        "key", "import", 
        key_commands.import_env,
        "Import API keys from environment variables"
    )
    
    registry.register_subcommand(
        "key", "export", 
        key_commands.export_env,
        "Export API keys to environment variables"
    )
    