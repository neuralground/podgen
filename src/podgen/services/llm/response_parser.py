import json
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def parse_json_response(response: str) -> Dict[str, Any]:
    """Extract and parse JSON from response text."""
    try:
        # Try direct JSON parsing first
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to find JSON-like content
        matches = re.findall(r'\{[\s\S]*\}', response)
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
        
        raise ValueError("No valid JSON found in response")

def extract_dialogue_from_text(text: str) -> List[Dict[str, str]]:
    """Extract dialogue turns from plain text format."""
    dialogue = []
    current_speaker = None
    current_content = []
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Look for speaker markers
        if ':' in line and len(line.split(':')[0].split()) <= 3:  # Reasonable speaker name length
            # Save previous turn if exists
            if current_speaker and current_content:
                dialogue.append({
                    'speaker': current_speaker,
                    'content': ' '.join(current_content).strip()
                })
            
            # Start new turn
            parts = line.split(':', 1)
            current_speaker = parts[0].strip()
            current_content = [parts[1].strip()] if len(parts) > 1 else []
        elif current_speaker and line:
            current_content.append(line)
    
    # Add final turn
    if current_speaker and current_content:
        dialogue.append({
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        })
    
    return dialogue
