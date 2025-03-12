#!/usr/bin/env python3
"""
Fix for syntax error in podcast_generator.py
This script corrects the syntax error introduced by the previous fix.
"""

import os
import sys
from pathlib import Path

def fix_podcast_generator():
    """Fix the syntax error in podcast_generator.py."""
    # Locate the project directory
    if os.path.exists("src/podgen"):
        base_dir = Path(".")
    elif os.path.exists("../src/podgen"):
        base_dir = Path("..")
    else:
        print("ERROR: Cannot find Podgen source directory.")
        return False
    
    # Path to podcast_generator.py
    podcast_path = base_dir / "src" / "podgen" / "services" / "podcast_generator.py"
    
    if not podcast_path.exists():
        print(f"ERROR: Cannot find {podcast_path}")
        return False
    
    # Read current content
    with open(podcast_path, 'r') as f:
        lines = f.readlines()
    
    # Find problematic section and fix it
    fixed_lines = []
    in_try_block = False
    in_dialogue_section = False
    dialogue_section_indent = 0
    
    for line in lines:
        # Check if we're in the dialogue generation section (Step 2)
        if "# 2. Generate conversation" in line:
            in_dialogue_section = True
            dialogue_section_indent = len(line) - len(line.lstrip())
        
        # Track try blocks
        if in_dialogue_section and "try:" in line:
            in_try_block = True
            
        # Check for incorrect except outside of try block
        if in_dialogue_section and not in_try_block and "except ValueError as e:" in line:
            # Skip this incorrect line
            continue
            
        # If we see a new section header, we're out of the dialogue section
        if in_dialogue_section and line.strip().startswith("# 3."):
            in_dialogue_section = False
            
        # Keep valid lines
        fixed_lines.append(line)
    
    # Write fixed content back to file
    with open(podcast_path, 'w') as f:
        f.writelines(fixed_lines)
    
    print(f"Fixed syntax error in {podcast_path}")
    
    # Now let's apply a proper fix with correct indentation
    # First let's read the fixed file again
    with open(podcast_path, 'r') as f:
        content = f.read()
    
    # Look for dialogue generation pattern (simplified)
    import re
    dialogue_pattern = r'(# 2\. Generate conversation.*?\n.*?dialogue = await self\.conversation\.generate_dialogue\(.*?\n.*?if not dialogue or not dialogue\.turns:\n.*?raise ValueError\([^)]*\))'
    
    match = re.search(dialogue_pattern, content, re.DOTALL)
    if not match:
        print("WARNING: Could not find dialogue generation pattern to apply fallback logic")
        return True  # We at least fixed the syntax error
    
    # Wrap with proper try-except
    original_code = match.group(1)
    indentation = "            "  # Common indentation in this file
    
    # Create the fallback handling code
    fallback_code = f"""            try:
{indentation}    # Generate dialogue with normal settings
{indentation}    dialogue = await self.conversation.generate_dialogue(
{indentation}        analysis,
{indentation}        config
{indentation}    )
{indentation}    
{indentation}    if not dialogue or not dialogue.turns:
{indentation}        raise ValueError("Dialogue generation returned no results")
{indentation}    
{indentation}    logger.info(f"Generated {{len(dialogue.turns)}} dialogue turns")
{indentation}        
{indentation}except ValueError as e:
{indentation}    # Fallback for dialogue generation errors
{indentation}    logger.warning(f"Primary dialogue generation failed: {{e}}")
{indentation}    
{indentation}    # Only attempt fallback for specific errors
{indentation}    if "Failed to generate valid conversation" in str(e) or "dialogue generation returned no results" in str(e).lower():
{indentation}        logger.info("Attempting fallback dialogue generation with simplified settings")
{indentation}        
{indentation}        # Simplify config for fallback attempt
{indentation}        fallback_config = config.copy()
{indentation}        fallback_config["style"] = "casual"  # Switch to casual style
{indentation}        fallback_config["target_duration"] = min(15, config.get("target_duration", 15))  # Reduce length if needed
{indentation}        
{indentation}        try:
{indentation}            # Try with fallback config
{indentation}            dialogue = await self.conversation.generate_dialogue(
{indentation}                analysis,
{indentation}                fallback_config
{indentation}            )
{indentation}            
{indentation}            if not dialogue or not dialogue.turns:
{indentation}                raise ValueError("Fallback dialogue generation failed to produce valid results")
{indentation}                
{indentation}            logger.info(f"Fallback dialogue generation succeeded with {{len(dialogue.turns)}} turns")
{indentation}        except Exception as fallback_error:
{indentation}            # Re-raise with more context
{indentation}            logger.error(f"Fallback dialogue generation also failed: {{fallback_error}}")
{indentation}            raise ValueError(f"Dialogue generation failed after fallback attempt") from e
{indentation}    else:
{indentation}        # Re-raise original error if not specifically a dialogue validation issue
{indentation}        raise"""
    
    # Need to identify correct replacement pattern based on existing code
    # Look for the try-except pattern in generate_podcast
    try_pattern = r'(\s+try:\s+.*?# Generate with updated word target.*?config_with_target = .*?\s+# Generate dialogue using prompt builder.*?\s+dialogue_turns = await self\.llm\.generate_dialogue\(.*?\s+if not dialogue_turns:.*?\s+continue.*?\s+# Process turns with validation)\s+'
    
    # Find better pattern that matches the dialogue generation in podcast_generator.py
    dialogue_gen_pattern = r'(\s+# 2\. Generate conversation.*?\n\s+if debug:.*?\n\s+logger\.debug\("Stage 2 - Conversation Generation"\)\s+report_progress\(\'conversation\', 0\.0, 0\.3\))'
    
    try_match = re.search(dialogue_gen_pattern, content, re.DOTALL)
    if try_match:
        # Found the right section
        dialogue_gen_code = try_match.group(1)
        
        # Replace with modified code that includes our fallback
        replacement_code = f"{dialogue_gen_code}\n\n{fallback_code}"
        content = content.replace(dialogue_gen_code, replacement_code)
        
        # Write the fixed content back
        with open(podcast_path, 'w') as f:
            f.write(content)
        
        print("Successfully applied fallback logic with correct syntax")
        return True
    else:
        print("WARNING: Could not find appropriate section to add fallback logic")
        return True  # We at least fixed the syntax error

def main():
    """Apply the fix."""
    success = fix_podcast_generator()
    
    if success:
        print("\nFix applied successfully! Syntax error should be resolved.")
        print("You can now try running Podgen again.")
    else:
        print("\nFailed to apply the fix automatically.")
        print("You may need to manually fix podcast_generator.py.")
        print("Look for an 'except ValueError as e:' statement that's outside of a try block.")

if __name__ == "__main__":
    main()
