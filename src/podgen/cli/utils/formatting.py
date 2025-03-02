"""CLI output formatting utilities."""

import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict, Union
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

def format_file_size(size_bytes: int) -> str:
    """Format file size to a human-readable string."""
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    elif size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.1f} MB"
    elif size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.1f} KB"
    else:
        return f"{size_bytes} bytes"

def format_duration(seconds: float) -> str:
    """Format duration in seconds to MM:SS format."""
    minutes = int(seconds) // 60
    seconds = int(seconds) % 60
    return f"{minutes}:{seconds:02d}"

def format_timestamp(timestamp: Union[datetime.datetime, float, str]) -> str:
    """Format timestamp to a human-readable string."""
    if isinstance(timestamp, datetime.datetime):
        dt = timestamp
    elif isinstance(timestamp, (int, float)):
        dt = datetime.datetime.fromtimestamp(timestamp)
    elif isinstance(timestamp, str):
        try:
            dt = datetime.datetime.fromisoformat(timestamp)
        except ValueError:
            try:
                dt = datetime.datetime.fromtimestamp(float(timestamp))
            except (ValueError, TypeError):
                return str(timestamp)
    else:
        return str(timestamp)
    
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def create_status_table(
    items: List[Dict[str, Any]], 
    title: str = "Status",
    status_column: str = "status"
) -> Table:
    """Create a rich table with status indicators."""
    table = Table(title=title)
    
    # Determine columns from the first item
    if not items:
        table.add_column("No Items")
        return table
    
    columns = list(items[0].keys())
    
    # Ensure status column exists
    if status_column not in columns:
        status_column = None
    
    # Add columns to table
    for column in columns:
        justify = "right" if column.lower() in ["id", "size", "duration"] else "left"
        style = "cyan" if column.lower() == "id" else None
        table.add_column(column.capitalize(), justify=justify, style=style)
    
    # Add rows
    for item in items:
        row = []
        for column in columns:
            value = item.get(column, "")
            
            # Format values based on column type
            if column.lower() == "size" and isinstance(value, (int, float)):
                value = format_file_size(value)
            elif column.lower() in ["created", "modified", "date"] and not isinstance(value, str):
                value = format_timestamp(value)
            elif column.lower() == "duration" and isinstance(value, (int, float)):
                value = format_duration(value)
            
            # Format status column with color
            if column == status_column:
                if str(value).lower() in ["success", "completed", "active"]:
                    value = f"[green]{value}"
                elif str(value).lower() in ["pending", "generating", "processing"]:
                    value = f"[yellow]{value}"
                elif str(value).lower() in ["error", "failed"]:
                    value = f"[red]{value}"
            
            row.append(str(value))
        
        table.add_row(*row)
    
    return table

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def format_path(path: Path, relative_to: Optional[Path] = None) -> str:
    """Format a path for display, optionally making it relative."""
    if not relative_to:
        return str(path)
    
    try:
        return str(path.relative_to(relative_to))
    except ValueError:
        return str(path)

def display_markdown(console: Console, text: str) -> None:
    """Display markdown-formatted text."""
    console.print(Markdown(text))

def create_metadata_panel(
    metadata: Dict[str, Any], 
    title: str = "Metadata",
    exclude_keys: Optional[List[str]] = None
) -> Panel:
    """Create a panel displaying metadata."""
    exclude_keys = exclude_keys or []
    
    # Format metadata as string
    lines = []
    for key, value in metadata.items():
        if key in exclude_keys or value is None:
            continue
            
        # Format based on value type
        if isinstance(value, (int, float)) and key.lower() in ["size", "bytes"]:
            value = format_file_size(value)
        elif isinstance(value, (datetime.datetime, float)) and key.lower() in ["date", "time", "created", "modified"]:
            value = format_timestamp(value)
        elif isinstance(value, Path):
            value = str(value)
        elif isinstance(value, dict):
            value = "{...}"  # Indicate nested structure
        elif isinstance(value, list) and len(value) > 3:
            value = f"[{', '.join(str(v) for v in value[:3])}...]"
            
        lines.append(f"{key}: {value}")
    
    content = "\n".join(lines) if lines else "No metadata available"
    return Panel(content, title=title)
