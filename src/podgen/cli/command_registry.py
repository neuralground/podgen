"""Command registry system for podgen CLI."""

import logging
import inspect
from typing import Dict, List, Any, Callable, Optional, Awaitable, Union
from rich.console import Console
import asyncio
import functools

logger = logging.getLogger(__name__)

# Command handler type - can be sync or async
CommandHandler = Union[
    Callable[[Console, List[str]], Any],
    Callable[[Console, List[str]], Awaitable[Any]]
]

class Command:
    """Represents a CLI command with metadata."""
    
    def __init__(
        self, 
        handler: CommandHandler,
        name: str,
        help_text: str,
        subcommands: Optional[Dict[str, 'Command']] = None
    ):
        self.handler = handler
        self.name = name
        self.help_text = help_text
        self.subcommands = subcommands or {}
        
    @property
    def is_async(self) -> bool:
        """Check if the handler is asynchronous."""
        return inspect.iscoroutinefunction(self.handler)
    
    def add_subcommand(self, name: str, command: 'Command') -> None:
        """Add a subcommand."""
        self.subcommands[name] = command
        
    def get_subcommand(self, name: str) -> Optional['Command']:
        """Get a subcommand by name."""
        return self.subcommands.get(name)

    async def execute(self, console: Console, args: List[str]) -> Any:
        """Execute the command handler with arguments."""
        try:
            if self.is_async:
                return await self.handler(console, args)
            else:
                result = self.handler(console, args)
                # Handle case where a non-async handler returns a coroutine
                if inspect.iscoroutine(result):
                    return await result
                return result
        except Exception as e:
            logger.error(f"Error executing command {self.name}: {e}")
            console.print(f"[red]Error executing command: {str(e)}")
            return None

class CommandRegistry:
    """Registry for CLI commands."""
    
    def __init__(self):
        self.commands: Dict[str, Command] = {}
        
    def register(self, 
                 name: str, 
                 handler: CommandHandler, 
                 help_text: str = "") -> None:
        """Register a top-level command."""
        self.commands[name] = Command(handler, name, help_text)
        
    def register_subcommand(self, 
                           parent: str, 
                           name: str, 
                           handler: CommandHandler,
                           help_text: str = "") -> None:
        """Register a subcommand under a parent command."""
        if parent not in self.commands:
            # Create a placeholder parent command
            self.commands[parent] = Command(
                self._default_parent_handler,
                parent,
                f"{parent} commands"
            )
            
        self.commands[parent].add_subcommand(
            name,
            Command(handler, name, help_text)
        )
        
    def _default_parent_handler(self, console: Console, args: List[str]) -> None:
        """Default handler for parent commands with no explicit handler."""
        if not args:
            console.print(f"[red]Please specify a subcommand.")
            return self.show_help(console, args)
            
        subcommand = args[0]
        parent_cmd = console.input.split()[0][1:]  # Extract parent command from input
        
        console.print(f"[red]Unknown {parent_cmd} subcommand: {subcommand}")
        return self.show_help(console, [parent_cmd])
    
    def get_command(self, name: str) -> Optional[Command]:
        """Get a command by name."""
        return self.commands.get(name)
    
    def show_help(self, console: Console, args: List[str]) -> None:
        """Show help for commands."""
        if not args:
            # Show all top-level commands
            console.print("[bold]Available commands:[/bold]")
            for name, cmd in sorted(self.commands.items()):
                console.print(f"  /{name} - {cmd.help_text}")
            return
            
        # Show help for a specific command
        command_name = args[0]
        command = self.get_command(command_name)
        
        if not command:
            console.print(f"[red]Unknown command: {command_name}")
            return
        
        console.print(f"[bold]/{command_name}[/bold] - {command.help_text}")
        
        if command.subcommands:
            console.print("\n[bold]Subcommands:[/bold]")
            for subname, subcmd in sorted(command.subcommands.items()):
                console.print(f"  /{command_name} {subname} - {subcmd.help_text}")
    
    async def execute(self, console: Console, input_text: str) -> Any:
        """Execute a command from user input."""
        if not input_text.startswith('/'):
            return None
                
        parts = input_text[1:].split()  # Remove leading slash
        if not parts:
            return None
                
        command_name = parts[0].lower()
        args = parts[1:]
            
        command = self.get_command(command_name)
        if not command:
            console.print(f"[red]Unknown command: {command_name}")
            return None
                
        # Check for subcommands
        if args and command.subcommands:
            subcommand_name = args[0].lower()
            subcommand = command.get_subcommand(subcommand_name)
                
            if subcommand:
                return await subcommand.execute(console, args[1:])
            
        # Execute the main command
        return await command.execute(console, args)

# Command decorator functions for easier registration
def command(registry: CommandRegistry, name: str, help_text: str = ""):
    """Decorator for registering a command."""
    def decorator(func):
        registry.register(name, func, help_text)
        return func
    return decorator

def subcommand(registry: CommandRegistry, parent: str, name: str, help_text: str = ""):
    """Decorator for registering a subcommand."""
    def decorator(func):
        registry.register_subcommand(parent, name, func, help_text)
        return func
    return decorator
