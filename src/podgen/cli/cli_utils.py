"""Enhanced CLI completion using readline."""

import os
import glob
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

def path_completer(prefix: str) -> List[str]:
    """Complete file and directory paths."""
    print(f"DEBUG: path_completer called with prefix='{prefix}'")
    
    try:
        # Handle empty prefix
        if not prefix:
            prefix = '.'
        
        # Expand user directory if needed
        if prefix.startswith('~'):
            prefix = os.path.expanduser(prefix)
        
        # Get the directory to search in
        if os.path.isabs(prefix):
            base_dir = os.path.dirname(prefix)
            file_prefix = os.path.basename(prefix)
        else:
            # For relative paths, join with current directory
            abs_prefix = os.path.abspath(prefix)
            base_dir = os.path.dirname(abs_prefix)
            file_prefix = os.path.basename(prefix)
        
        print(f"DEBUG: base_dir='{base_dir}', file_prefix='{file_prefix}'")
        
        # If base_dir is empty, use current directory
        if not base_dir:
            base_dir = '.'
        
        # Get directory entries
        entries = os.listdir(base_dir)
        matches = []
        
        for entry in entries:
            if entry.startswith(file_prefix):
                if base_dir == '.':
                    full_path = entry
                else:
                    full_path = os.path.join(os.path.dirname(prefix), entry)
                
                # Add trailing slash for directories
                if os.path.isdir(os.path.join(base_dir, entry)):
                    matches.append(f"{full_path}/")
                else:
                    matches.append(full_path)
        
        print(f"DEBUG: Found matches: {matches}")
        return sorted(matches, key=lambda x: (not x.endswith('/'), x.lower()))
        
    except Exception as e:
        print(f"DEBUG: Path completion error: {str(e)}")
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
    try:
        print(f"\nDEBUG: Completion called with text='{text}', state={state}")
        
        # Get the current line buffer to understand context
        import readline
        buffer = readline.get_line_buffer()
        print(f"DEBUG: Full line buffer: '{buffer}'")
        
        if state == 0:
            # Check if we're in an "add source" context
            if buffer.startswith('/add source'):
                # Extract just the path part for completion
                path_prefix = text
                print(f"DEBUG: Path completion with prefix='{path_prefix}'")
                matches = path_completer(path_prefix)
                print(f"DEBUG: Path matches: {matches}")
                # Don't add command prefix - return raw matches
                get_completion.matches = matches
            else:
                parts = text.split()
                if not text or text.startswith('/'):
                    matches = command_completer(text, {})
                    get_completion.matches = matches
                else:
                    get_completion.matches = []
        
        try:
            match = get_completion.matches[state]
            print(f"DEBUG: Returning match: '{match}' for state {state}")
            return match
        except (AttributeError, IndexError):
            print(f"DEBUG: No match for state {state}")
            return None
            
    except Exception as e:
        print(f"DEBUG: Completion error: {str(e)}")
        return None

def setup_completion() -> None:
    """Set up completion for the CLI."""
    import readline
    
    # Define the prompt display function
    def refresh_prompt(prompt):
        readline.redisplay()
    
    # Set up proper line editing
    readline.parse_and_bind('set editing-mode emacs')
    readline.parse_and_bind('set show-all-if-ambiguous on')
    readline.parse_and_bind('set completion-ignore-case on')
    readline.parse_and_bind('set mark-directories on')
    readline.parse_and_bind('set mark-symlinked-directories on')
    
    # Set completer function
    readline.set_completer(get_completion)
    
    # Set completer delimiters
    readline.set_completer_delims(' \t\n')
    
    # Set the pre-input hook to handle prompt redisplay
    readline.set_pre_input_hook(lambda: refresh_prompt("podgen> "))
    
    # Configure based on readline implementation
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')

# Initialize completion on import
setup_completion()

