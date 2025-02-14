"""Enhanced CLI completion using argcomplete."""

import os
import glob
from pathlib import Path
from typing import List, Optional, Dict, Set, Any
import logging

logger = logging.getLogger(__name__)

def path_completer(prefix: str) -> List[str]:
    """Complete file and directory paths."""
    if prefix.startswith('~'):
        prefix = os.path.expanduser(prefix)
    
    base_dir = os.path.dirname(prefix) if prefix else '.'
    if not base_dir:
        base_dir = '.'
        
    try:
        entries = os.listdir(base_dir)
        matches = []
        
        for entry in entries:
            full_path = os.path.join(base_dir, entry)
            # Only include entries that match the prefix
            if full_path.startswith(prefix) or not prefix:
                # Add trailing slash for directories
                if os.path.isdir(full_path):
                    matches.append(f"{full_path}/")
                else:
                    matches.append(full_path)
        
        # Sort matches with directories first
        matches.sort(key=lambda x: (not x.endswith('/'), x.lower()))
        return matches
        
    except OSError:
        return []

def command_completer(prefix: str, parsed_args: Dict[str, Any]) -> List[str]:
    """Complete commands and subcommands."""
    commands = {
        "add": ["source", "conversation"],
        "list": ["sources", "conversations"],
        "remove": ["source", "conversation", "all sources", "all conversations"],
        "play": ["conversation"],
        "show": ["conversation"],
        "help": [],
        "quit": [],
        "exit": [],
        "bye": []
    }
    
    # Remove leading slash if present
    clean_prefix = prefix.lstrip('/')
    
    # If empty prefix, show all commands
    if not clean_prefix:
        return [f"/{cmd}" for cmd in commands.keys()]
    
    # If prefix has no space, complete command
    if ' ' not in clean_prefix:
        return [
            f"/{cmd}" for cmd in commands.keys()
            if cmd.startswith(clean_prefix)
        ]
    
    # If we have "add source", use path completion
    if clean_prefix.startswith("add source"):
        path_part = clean_prefix[len("add source"):].lstrip()
        return path_completer(path_part)
    
    # Otherwise complete subcommands
    cmd_parts = clean_prefix.split()
    if len(cmd_parts) == 1 and cmd_parts[0] in commands:
        return [f"/{cmd_parts[0]} {sub}" for sub in commands[cmd_parts[0]]]
        
    return []

def get_completion(text: str, state: int) -> Optional[str]:
    """Get completion for current input."""
    if state == 0:
        # Split input into command and args
        parts = text.split()
        
        # Use appropriate completer based on input
        if not text or text.startswith('/'):
            matches = command_completer(text, {})
        elif len(parts) >= 2 and parts[0] == '/add' and parts[1] == 'source':
            # Pass the partial path to path completer
            path_part = ' '.join(parts[2:]) if len(parts) > 2 else ''
            matches = path_completer(path_part)
        else:
            matches = []
            
        # Store matches for subsequent states
        get_completion.matches = matches
    
    try:
        return get_completion.matches[state]
    except (AttributeError, IndexError):
        return None

def setup_completion() -> None:
    """Set up completion for the CLI."""
    import readline
    
    # Set completer function
    readline.set_completer(get_completion)
    
    # Set word delimiters
    readline.set_completer_delims(' \t\n')
    
    # Set completion mode
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')

# Initialize completion on import
setup_completion()

