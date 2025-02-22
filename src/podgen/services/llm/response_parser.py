import json
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def parse_json_response(response: str) -> Dict[str, Any]:
    """Extract and parse JSON from response text with enhanced error handling."""
    try:
        # Try direct JSON parsing first
        return json.loads(response)
    except json.JSONDecodeError:
        # Look for JSON-like content with more flexible pattern matching
        # First try standard JSON object pattern
        matches = re.findall(r'\{[\s\S]*\}', response)
        for match in matches:
            try:
                return json.loads(match)
            except:
                continue
        
        # Try array pattern if no valid objects found
        matches = re.findall(r'\[[\s\S]*\]', response)
        for match in matches:
            try:
                return {"dialogue": json.loads(match)}
            except:
                continue
        
        # If no JSON found, try to parse structured text as dialogue
        return {"dialogue": extract_dialogue_from_text(response)}

def extract_dialogue_from_text(text: str) -> List[Dict[str, str]]:
    """Extract dialogue turns from plain text format with enhanced detection."""
    dialogue = []
    current_speaker = None
    current_content = []
    
    # Handle both "Speaker:" and "Speaker :" formats
    speaker_pattern = re.compile(r'^([^:]{1,30})\s*:\s*(.*)$')
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Look for speaker markers
        match = speaker_pattern.match(line)
        if match:
            # Save previous turn if exists
            if current_speaker and current_content:
                dialogue.append({
                    'speaker': current_speaker,
                    'content': ' '.join(current_content).strip()
                })
            
            # Start new turn
            current_speaker = match.group(1).strip()
            current_content = [match.group(2).strip()] if match.group(2) else []
        elif current_speaker and line:
            # Check if this line starts a new speaker without colon
            new_speaker_match = re.match(r'^([A-Za-z\s]{2,20})(\s+)(.+)$', line)
            if new_speaker_match and len(new_speaker_match.group(1).strip()) < 20:
                # Looks like a new speaker without colon
                if current_speaker and current_content:
                    dialogue.append({
                        'speaker': current_speaker,
                        'content': ' '.join(current_content).strip()
                    })
                current_speaker = new_speaker_match.group(1).strip()
                current_content = [new_speaker_match.group(3)]
            else:
                current_content.append(line)
    
    # Add final turn
    if current_speaker and current_content:
        dialogue.append({
            'speaker': current_speaker,
            'content': ' '.join(current_content).strip()
        })
    
    # Filter out invalid turns
    dialogue = [
        turn for turn in dialogue
        if turn['speaker'] and turn['content'] and
        len(turn['speaker']) < 30 and  # Reasonable speaker name length
        len(turn['content'].split()) > 10  # Minimum content length
    ]
    
    return dialogue
