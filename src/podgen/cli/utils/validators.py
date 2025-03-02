"""Input validation utilities for CLI commands."""

import re
import os
from pathlib import Path
from typing import Optional, Union, Tuple, List, Dict, Any

def validate_filename(filename: str) -> Tuple[bool, str]:
    """Validate a filename for path traversal and invalid characters.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for empty filename
    if not filename or not filename.strip():
        return False, "Filename cannot be empty"
    
    # Check for path traversal
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        return False, "Path traversal not allowed"
    
    # Check for invalid characters
    invalid_chars = r'[<>:"|?*]'
    if re.search(invalid_chars, filename):
        return False, "Filename contains invalid characters"
    
    return True, ""

def validate_path(path: Union[str, Path], must_exist: bool = False) -> Tuple[bool, str]:
    """Validate a path for existence and permissions.
    
    Args:
        path: The path to validate
        must_exist: Whether the path must already exist
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        path_obj = Path(path).resolve()
        
        # Check if path exists if required
        if must_exist and not path_obj.exists():
            return False, f"Path does not exist: {path}"
        
        # Check for read permissions if exists
        if path_obj.exists() and not os.access(path_obj, os.R_OK):
            return False, f"No read permission for path: {path}"
            
        return True, ""
    except Exception as e:
        return False, f"Invalid path: {e}"

def validate_url(url: str) -> Tuple[bool, str]:
    """Validate URL format.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic URL format validation
    url_pattern = r'^(https?|ftp):\/\/[^\s/$.?#].[^\s]*$'
    if not re.match(url_pattern, url):
        return False, "Invalid URL format"
    
    return True, ""

def validate_api_key(key: str, key_type: str) -> Tuple[bool, str]:
    """Validate API key format based on type.
    
    Args:
        key: The API key to validate
        key_type: Type of API key (openai, elevenlabs, etc.)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "API key cannot be empty"
    
    # Validate OpenAI key
    if key_type.lower() == 'openai':
        if not key.startswith('sk-') or len(key) < 20:
            return False, "Invalid OpenAI API key format"
    
    # Validate ElevenLabs key
    elif key_type.lower() == 'elevenlabs':
        if len(key) < 20:
            return False, "ElevenLabs API key seems too short"
    
    # Generic length check for other key types
    elif len(key) < 10:
        return False, f"API key seems too short for {key_type}"
    
    return True, ""

def validate_id(id_str: str, id_type: str = "ID") -> Tuple[bool, int, str]:
    """Validate and convert an ID string to integer.
    
    Args:
        id_str: The ID string to validate
        id_type: Type of ID for error messages
        
    Returns:
        Tuple of (is_valid, id_value, error_message)
    """
    try:
        id_value = int(id_str)
        if id_value < 0:
            return False, -1, f"{id_type} cannot be negative"
        return True, id_value, ""
    except ValueError:
        return False, -1, f"{id_type} must be a number"

def validate_duration(duration_str: str) -> Tuple[bool, float, str]:
    """Validate and convert a duration string to seconds.
    
    Args:
        duration_str: Duration string (e.g., "5:30" for 5 minutes 30 seconds)
        
    Returns:
        Tuple of (is_valid, seconds, error_message)
    """
    # Check if it's already just a number of seconds
    try:
        seconds = float(duration_str)
        if seconds < 0:
            return False, 0, "Duration cannot be negative"
        return True, seconds, ""
    except ValueError:
        pass
    
    # Try MM:SS format
    try:
        if ':' in duration_str:
            parts = duration_str.split(':')
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                if minutes < 0 or seconds < 0 or seconds >= 60:
                    return False, 0, "Invalid duration format (use MM:SS or seconds)"
                return True, minutes * 60 + seconds, ""
    except ValueError:
        pass
    
    return False, 0, "Invalid duration format (use MM:SS or seconds)"

def validate_command_args(args: List[str], required_count: int, 
                          usage_msg: str) -> Tuple[bool, str]:
    """Validate command arguments.
    
    Args:
        args: List of command arguments
        required_count: Number of required arguments
        usage_msg: Usage message to show on error
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(args) < required_count:
        return False, usage_msg
    return True, ""

def validate_choice(value: str, choices: List[str], 
                    case_sensitive: bool = False) -> Tuple[bool, str]:
    """Validate that a value is one of the allowed choices.
    
    Args:
        value: The value to validate
        choices: List of allowed choices
        case_sensitive: Whether comparison should be case-sensitive
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not case_sensitive:
        value = value.lower()
        choices_lower = [c.lower() for c in choices]
        if value not in choices_lower:
            return False, f"Value must be one of: {', '.join(choices)}"
    else:
        if value not in choices:
            return False, f"Value must be one of: {', '.join(choices)}"
    
    return True, ""

def parse_key_value_args(args: List[str]) -> Dict[str, str]:
    """Parse a list of key=value arguments into a dictionary.
    
    Args:
        args: List of arguments in the format "key=value"
        
    Returns:
        Dictionary of parsed key-value pairs
    """
    result = {}
    for arg in args:
        if '=' in arg:
            key, value = arg.split('=', 1)
            result[key.strip()] = value.strip()
    return result
