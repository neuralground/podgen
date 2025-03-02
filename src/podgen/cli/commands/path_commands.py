"""Path management commands for podgen CLI."""

import logging
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from pathlib import Path
import os
import shutil

from ...config import settings

logger = logging.getLogger(__name__)

class PathCommands:
    """Commands for managing podgen file paths."""
    
    def __init__(self, paths=None):
        """Initialize with path manager."""
        self.paths = paths or settings.paths
    
    async def show(self, console: Console, args: List[str]) -> None:
        """Show current file path configuration."""
        try:
            console.print("[bold]Current Paths Configuration:[/bold]\n")
            
            # Show base directory
            console.print(f"Base directory: {self.paths.base_dir}")
            
            # Create a table for paths
            table = Table(show_header=True)
            table.add_column("Category", style="green")
            table.add_column("Path", style="blue")
            table.add_column("Status", style="yellow")
            
            # Add rows for each path
            for name, path in sorted(self.paths.subdirs.items()):
                # Check directory status
                if path.exists():
                    if os.access(path, os.W_OK):
                        status = "[green]Ready (writable)"
                    else:
                        status = "[red]Ready (read-only)"
                else:
                    status = "[red]Not found"
                
                table.add_row(name, str(path), status)
            
            console.print(table)
            
            # Show environment variables
            console.print("\n[bold]Environment Settings:[/bold]")
            console.print(f"PODGEN_DIR: {os.environ.get('PODGEN_DIR', 'Not set')}")
            console.print(f"Current process working directory: {os.getcwd()}")
            
        except Exception as e:
            logger.error(f"Error showing paths: {e}")
            console.print(f"[red]Error showing paths: {str(e)}")
    
    async def list(self, console: Console, args: List[str]) -> None:
        """List files in a specific directory."""
        try:
            if not args:
                console.print("[red]Please specify a category")
                console.print("Usage: /paths list <category> [pattern]")
                return
                
            category = args[0]
            pattern = args[1] if len(args) > 1 else "*"
            
            try:
                path = self.paths.get_path(category)
                files = list(path.glob(pattern))
            except Exception as e:
                console.print(f"[red]Error accessing {category}: {e}")
                return
                
            # Format the output
            if not files:
                console.print(f"No files found in {category} matching '{pattern}'")
                return
                
            console.print(f"[bold]Files in {category} matching '{pattern}':[/bold]")
            
            # Create a table for better formatting
            table = Table(show_header=True)
            table.add_column("Filename", style="green")
            table.add_column("Size", style="blue", justify="right")
            table.add_column("Last Modified", style="yellow")
            
            # Get file details and sort by modification time (newest first)
            file_details = []
            for file in files:
                if file.is_file():
                    try:
                        size = file.stat().st_size
                        mtime = file.stat().st_mtime
                        file_details.append((file, size, mtime))
                    except Exception:
                        file_details.append((file, 0, 0))
                        
            # Sort by modification time (newest first)
            file_details.sort(key=lambda x: x[2], reverse=True)
            
            # Add rows to the table
            import time
            for file, size, mtime in file_details:
                # Format size
                if size > 1_000_000:
                    size_str = f"{size/1_000_000:.1f} MB"
                elif size > 1_000:
                    size_str = f"{size/1_000:.1f} KB"
                else:
                    size_str = f"{size} bytes"
                    
                # Format modification time
                mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
                
                table.add_row(file.name, size_str, mtime_str)
                
            console.print(table)
            
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            console.print(f"[red]Error listing files: {str(e)}")
    
    async def clear(self, console: Console, args: List[str]) -> None:
        """Clear files in a specific directory."""
        try:
            if not args:
                console.print("[red]Please specify a category")
                console.print("Usage: /paths clear <category> [--force]")
                return
                
            category = args[0]
            force = "--force" in args
            
            try:
                path = self.paths.get_path(category)
                if not path.exists():
                    console.print(f"[yellow]Directory {category} does not exist.")
                    return
            except Exception as e:
                console.print(f"[red]Error accessing {category}: {e}")
                return
                
            # Count files before clearing
            files = list(path.glob("*"))
            file_count = sum(1 for f in files if f.is_file())
            dir_count = sum(1 for f in files if f.is_dir())
            
            if file_count == 0 and dir_count == 0:
                console.print(f"[yellow]Directory {category} is already empty.")
                return
                
            # Confirm clearing unless forced
            if not force:
                message = f"Are you sure you want to clear {file_count} files and {dir_count} directories in {category}?"
                if not Confirm.ask(message):
                    console.print("[yellow]Operation cancelled.")
                    return
            
            # Clear the directory
            for item in files:
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except Exception as e:
                    logger.error(f"Failed to remove {item}: {e}")
                    console.print(f"[red]Failed to remove {item}: {e}")
            
            console.print(f"[green]Cleared {file_count} files and {dir_count} directories from {category}.")
            
        except Exception as e:
            logger.error(f"Error clearing directory: {e}")
            console.print(f"[red]Error clearing directory: {str(e)}")
    
    async def create(self, console: Console, args: List[str]) -> None:
        """Create a new directory category."""
        try:
            if not args:
                console.print("[red]Please specify a category name")
                console.print("Usage: /paths create <category>")
                return
                
            category = args[0]
            
            # Check if category already exists
            existing_path = self.paths.get_path(category)
            if category in self.paths.subdirs:
                console.print(f"[yellow]Category {category} already exists at {existing_path}")
                return
            
            # Create the new directory
            new_path = self.paths.base_dir / category
            new_path.mkdir(parents=True, exist_ok=True)
            
            # Register the new path
            self.paths.subdirs[category] = new_path
            
            console.print(f"[green]Created new category {category} at {new_path}")
            
        except Exception as e:
            logger.error(f"Error creating directory: {e}")
            console.print(f"[red]Error creating directory: {str(e)}")

    async def info(self, console: Console, args: List[str]) -> None:
        """Show detailed info about a path category."""
        try:
            if not args:
                console.print("[red]Please specify a category")
                console.print("Usage: /paths info <category>")
                return
                
            category = args[0]
            
            try:
                path = self.paths.get_path(category)
            except Exception as e:
                console.print(f"[red]Error accessing {category}: {e}")
                return
                
            if not path.exists():
                console.print(f"[red]Directory {category} does not exist.")
                return
                
            # Collect directory statistics
            file_count = 0
            dir_count = 0
            total_size = 0
            
            for item in path.glob("**/*"):
                if item.is_file():
                    file_count += 1
                    total_size += item.stat().st_size
                elif item.is_dir():
                    dir_count += 1
            
            # Format size for display
            if total_size > 1_000_000_000:
                size_str = f"{total_size/1_000_000_000:.2f} GB"
            elif total_size > 1_000_000:
                size_str = f"{total_size/1_000_000:.2f} MB"
            elif total_size > 1_000:
                size_str = f"{total_size/1_000:.2f} KB"
            else:
                size_str = f"{total_size} bytes"
                
            # Create a nicely formatted panel
            content = [
                f"Path: {path}",
                f"Files: {file_count}",
                f"Directories: {dir_count}",
                f"Total size: {size_str}",
                f"Permissions: {'Writable' if os.access(path, os.W_OK) else 'Read-only'}"
            ]
            
            panel = Panel("\n".join(content), title=f"[bold]{category} Info[/bold]")
            console.print(panel)
            
        except Exception as e:
            logger.error(f"Error getting path info: {e}")
            console.print(f"[red]Error getting path info: {str(e)}")

def register_commands(registry):
    """Register path commands with the command registry."""
    path_commands = PathCommands()
    
    # Register main command
    registry.register(
        "paths", 
        path_commands.show,
        "Manage file paths and storage locations"
    )
    
    # Register subcommands
    registry.register_subcommand(
        "paths", "show", 
        path_commands.show,
        "Show all path locations"
    )
    
    registry.register_subcommand(
        "paths", "list", 
        path_commands.list,
        "List files in a directory"
    )
    
    registry.register_subcommand(
        "paths", "clear", 
        path_commands.clear,
        "Clear files in a directory"
    )
    
    registry.register_subcommand(
        "paths", "create", 
        path_commands.create,
        "Create a new directory category"
    )
    
    registry.register_subcommand(
        "paths", "info", 
        path_commands.info,
        "Show detailed info about a path category"
    )
    