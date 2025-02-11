"""CLI help system implementation."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from typing import Dict, List

class CommandHelp:
    """Manages CLI command documentation and help display"""
    
    def __init__(self):
        self.commands: Dict[str, Dict[str, List[tuple]]] = {
            "Documents": {
                "description": "Manage your document collection",
                "commands": [
                    ("/add <file or URL>", "Add a document or webpage to your collection"),
                    ("/list", "Show all documents in your collection"),
                    ("/remove <id>", "Remove a document from your collection"),
                ]
            },
            "Conversation": {
                "description": "Configure conversation settings and formats",
                "commands": [
                    ("/formats", "List available conversation formats"),
                    ("/formats new", "Create a new conversation format"),
                    ("/formats delete <name>", "Delete a conversation format"),
                ]
            },
            "Speakers": {
                "description": "Manage speaker profiles and voices",
                "commands": [
                    ("/speakers", "List available speaker profiles"),
                    ("/speakers new", "Create a new speaker profile"),
                    ("/speakers delete <name>", "Delete a speaker profile"),
                ]
            },
            "Help": {
                "description": "Get help and information",
                "commands": [
                    ("/help", "Show this help message"),
                    ("/help <category>", "Show detailed help for a category"),
                    ("/help <command>", "Show detailed help for a specific command"),
                ]
            }
        }

    def show_help(self, console: Console, category: str = None, command: str = None) -> None:
        """Display help information"""
        if command:
            self._show_command_help(console, command)
        elif category:
            self._show_category_help(console, category)
        else:
            self._show_general_help(console)

    def _show_general_help(self, console: Console) -> None:
        """Show general help overview"""
        console.print("\n[bold]Podgen - AI Podcast Generator[/bold]\n")

        # Create category panels
        panels = []
        for category, info in self.commands.items():
            content = Text()
            content.append(f"{info['description']}\n\n", style="bright_black")

            # Add command summaries
            for cmd, desc in info["commands"]:
                content.append(f"{cmd}\n", style="green")

            panels.append(Panel(
                content,
                title=f"[bold]{category}[/bold]",
                title_align="left",
                border_style="bright_black"
            ))

        # Display in columns
        console.print(Columns(panels))

    def _show_category_help(self, console: Console, category: str) -> None:
        """Show detailed help for a category"""
        # Find category (case-insensitive)
        category_match = next(
            (cat for cat in self.commands.keys() 
             if cat.lower() == category.lower()),
            None
        )
        
        if not category_match:
            console.print(f"[red]Category not found: {category}")
            console.print("Available categories:")
            for cat in self.commands.keys():
                console.print(f"  {cat}")
            return
            
        info = self.commands[category_match]
        
        console.print(f"\n[bold]{category_match}[/bold]")
        console.print(f"{info['description']}\n")
        
        table = Table(show_header=True, header_style="bold")
        table.add_column("Command")
        table.add_column("Description")
        
        for cmd, desc in info["commands"]:
            table.add_row(cmd, desc)
            
        console.print(table)
        console.print()

    def _show_command_help(self, console: Console, command: str) -> None:
        """Show detailed help for a specific command"""
        # Remove leading slash if present
        if command.startswith("/"):
            command = command[1:]
            
        # Search for command
        found = False
        for category, info in self.commands.items():
            for cmd, desc in info["commands"]:
                cmd_name = cmd.split()[0][1:]  # Remove leading slash and args
                if cmd_name == command:
                    console.print(f"\n[bold]{cmd}[/bold]")
                    console.print(f"Category: {category}")
                    console.print(f"\n{desc}\n")
                    
                    # Add specific usage examples based on command
                    if command == "add":
                        console.print("Examples:")
                        console.print("  /add document.pdf")
                        console.print("  /add https://example.com/article")
                    elif command == "remove":
                        console.print("Examples:")
                        console.print("  /remove 1")
                        console.print("  /remove 42")
                    
                    found = True
                    break
        
        if not found:
            console.print(f"[red]Command not found: {command}")
            console.print("Use /help to see available commands")

