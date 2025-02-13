"""Enhanced CLI completion for both commands and paths."""

import os
import glob
import readline
from pathlib import Path
from typing import List, Optional, Dict, Set

class PodgenCompleter:
    """Handles command and path completion for the CLI."""
    
    def __init__(self):
        """Initialize the completer with known commands."""
        self.matches: List[str] = []
        self.commands = {
            "add": {"source", "conversation", "conversation debug"},
            "list": {"sources", "conversations"},
            "remove": {"source", "conversation", "all sources", "all conversations"},
            "play": {"conversation"},
            "show": {"conversation"},
            "help": set(),
            "bye": set()
        }
        
        # Build full command set including subcommands
        self.all_commands: Set[str] = set()
        for cmd, subcmds in self.commands.items():
            self.all_commands.add(f"/{cmd}")
            for subcmd in subcmds:
                self.all_commands.add(f"/{cmd} {subcmd}")
    
    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completion function."""
        if state == 0:
            # Start of a command
            if not text or text.startswith('/'):
                cmd_text = text[1:] if text.startswith('/') else text
                self.matches = [
                    cmd for cmd in self.all_commands 
                    if cmd.startswith(text or '/')
                ]
                self.matches.sort()
            
            # After "add source" command, do path completion
            elif text.startswith(('http://', 'https://')):
                self.matches = []
            else:
                line = readline.get_line_buffer()
                if line.startswith('/add source '):
                    # Handle path completion
                    if text.startswith('~'):
                        text = os.path.expanduser(text)
                    
                    if os.path.isabs(text):
                        directory = os.path.dirname(text)
                        partial = os.path.basename(text)
                    else:
                        directory = '.' if not text or '/' not in text else os.path.dirname(text)
                        partial = os.path.basename(text)
                    
                    if not directory:
                        directory = '.'
                    
                    try:
                        if partial:
                            pattern = os.path.join(directory, partial + '*')
                        else:
                            pattern = os.path.join(directory, '*')
                            
                        self.matches = glob.glob(pattern)
                        
                        # Add trailing slash to directories
                        self.matches = [
                            f"{match}/" if os.path.isdir(match) else match
                            for match in self.matches
                        ]
                        
                        # Sort with directories first
                        self.matches.sort(key=lambda x: (not x.endswith('/'), x.lower()))
                    except Exception:
                        self.matches = []
                else:
                    self.matches = []
        
        return self.matches[state] if state < len(self.matches) else None

def setup_path_completion() -> None:
    """Set up readline with command and path completion (legacy name for compatibility)."""
    setup_completion()

def setup_completion() -> None:
    """Set up readline with command and path completion."""
    # Create and register completer
    completer = PodgenCompleter()
    readline.set_completer(completer.complete)
    
    # Set up delimiters - remove '/' so paths aren't split
    readline.set_completer_delims(' \t\n`!@#$%^&*()=+[{]}\\|;:\'",<>?')
    
    # Set completion mode based on platform
    if 'libedit' in readline.__doc__:
        # macOS - use basic completion
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        # Linux/Unix - use filename completion
        readline.parse_and_bind('tab: complete')

__all__ = ['setup_completion', 'setup_path_completion', 'PodgenCompleter']

