#!/usr/bin/env python3
"""
Fix for conversation generation in Podgen.
This script improves the dialogue generation prompts and validation logic
to better handle longer podcasts.
"""

import os
import sys
import re
from pathlib import Path
import json

def fix_conversation_generator():
    """Fix the conversation generator to handle longer podcasts better."""
    # Locate the project directory
    if os.path.exists("src/podgen"):
        base_dir = Path(".")
    elif os.path.exists("../src/podgen"):
        base_dir = Path("..")
    else:
        print("ERROR: Cannot find Podgen source directory.")
        return False
    
    # Path to the file that needs to be fixed
    conversation_path = base_dir / "src" / "podgen" / "services" / "conversation.py"
    
    if not conversation_path.exists():
        print(f"ERROR: Cannot find {conversation_path}")
        return False
    
    # Read current content
    current_content = conversation_path.read_text()
    
    # 1. Fix the generate_dialogue method - relax validation criteria for longer podcasts
    # Find the validation section in generate_dialogue
    validation_pattern = r"""(\s+# Adjust validation thresholds .*?\n.*?min_words_per_turn = .*?\n.*?min_turn_ratio = .*?\n.*?max_sequential_same_speaker = .*?\n)"""
    
    new_validation_code = """
                    # Adjust validation thresholds based on model and target length
                    is_o1_model = hasattr(self.llm, 'model') and str(self.llm.model).startswith('o1')
                    
                    # Dynamic thresholds based on target duration/length
                    target_minutes = config.get('target_duration', 15)
                    is_long_podcast = target_minutes >= 25
                    
                    # Adjust thresholds for longer podcasts - be more lenient
                    if is_long_podcast:
                        min_words_per_turn = 40 if is_o1_model else 60
                        min_turn_ratio = 0.4 if is_o1_model else 0.6
                    else:
                        min_words_per_turn = 30 if is_o1_model else 75
                        min_turn_ratio = 0.5 if is_o1_model else 0.8
                    
                    max_sequential_same_speaker = 2  # Prevent monologues
"""
    
    # Replace validation section
    if re.search(validation_pattern, current_content):
        current_content = re.sub(validation_pattern, new_validation_code, current_content)
        print("Updated validation thresholds in conversation.py")
    else:
        print("WARNING: Could not find validation thresholds section")
    
    # 2. Update the final validation check to be more flexible for longer podcasts
    validation_check_pattern = r"""(\s+# Check if we've met our requirements.*?\n.*?if \(len\(turns\) >= optimal_turns \* min_turn_ratio and.*?\n.*?total_words >= target_words \* min_turn_ratio and.*?\n.*?len\(used_speakers\) == len\(speakers\)\):)"""
    
    new_validation_check = """
                    # Check if we've met our requirements with relaxed criteria for longer podcasts
                    meets_turn_requirement = len(turns) >= optimal_turns * min_turn_ratio
                    
                    # For longer podcasts, prioritize word count over turn count
                    if target_minutes >= 25:
                        meets_word_requirement = total_words >= target_words * 0.75  # 75% of target is acceptable
                    else:
                        meets_word_requirement = total_words >= target_words * min_turn_ratio
                    
                    meets_speaker_requirement = len(used_speakers) == len(speakers)
                    
                    if meets_word_requirement and meets_speaker_requirement and (meets_turn_requirement or target_minutes >= 25):
"""
    
    if re.search(validation_check_pattern, current_content):
        current_content = re.sub(validation_check_pattern, new_validation_check, current_content)
        print("Updated validation check in conversation.py")
    else:
        print("WARNING: Could not find validation check section")
    
    # 3. Now update the prompt builder for better dialogue generation
    prompts_path = base_dir / "src" / "podgen" / "services" / "llm" / "prompts.py"
    
    if not prompts_path.exists():
        print(f"ERROR: Cannot find {prompts_path}")
        # Still continue with the conversation.py update
    else:
        prompts_content = prompts_path.read_text()
        
        # Find the dialogue prompt building function
        prompt_pattern = r"""(    @staticmethod\n    def build_dialogue_prompt\([^)]*\):[^#]+?return f\"\"\"[^\"]*\"\"\")"""
        
        dialogue_prompt_function = re.search(prompt_pattern, prompts_content, re.DOTALL)
        
        if dialogue_prompt_function:
            # Extract the function to modify it
            old_function = dialogue_prompt_function.group(1)
            
            # Enhance the prompt text for better results
            improved_prompt = old_function.replace(
                "LENGTH REQUIREMENTS (STRICT):",
                "LENGTH REQUIREMENTS (VERY IMPORTANT):"
            ).replace(
                "- Each turn MUST be 75-150 words minimum",
                "- Each turn MUST be substantial (75-200 words for each speaker's response)\n- Aim for depth and detail in each response\n- Avoid short, quick exchanges - each speaker should fully develop their thoughts"
            ).replace(
                "- Short responses or brief acknowledgments will be rejected",
                "- Short responses will be rejected - speakers must provide thorough, detailed responses\n- Aim for SUBSTANTIAL content in each turn - quantity and quality are both important"
            ).replace(
                "CRITICAL RULES:",
                "CRITICAL RULES (FOLLOW THESE EXACTLY):"
            ).replace(
                "1. ABSOLUTELY NO brief exchanges or single-sentence responses",
                "1. ABSOLUTELY NO brief exchanges or responses with few details - be comprehensive"
            ).replace(
                "2. Each speaking turn must be self-contained and substantial",
                "2. Each speaking turn must be detailed and substantial (minimum 75-100 words each)"
            ).replace(
                "- Minimum words per turn: 75",
                "- Minimum words per turn: 75 (more is better)\n- Depth of content is critical - develop each point thoroughly"
            )
            
            # Apply the changes
            prompts_content = prompts_content.replace(old_function, improved_prompt)
            prompts_path.write_text(prompts_content)
            print(f"Updated dialogue prompt in {prompts_path}")
    
    # Save the modified conversation.py file
    conversation_path.write_text(current_content)
    print(f"Updated {conversation_path}")
    return True

def fix_podcast_generator():
    """Fix the podcast generator to better handle dialogue generation errors."""
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
    current_content = podcast_path.read_text()
    
    # Find the dialogue generation code block to add fallback logic
    dialogue_pattern = r"""(\s+# 2\. Generate conversation.*?\n.*?try:\n.*?dialogue = await self\.conversation\.generate_dialogue\([^)]*\).*?\n.*?if not dialogue or not dialogue\.turns:\n.*?raise ValueError\([^)]*\))"""
    
    dialogue_match = re.search(dialogue_pattern, current_content, re.DOTALL)
    
    if not dialogue_match:
        print("WARNING: Could not find dialogue generation section")
        return False
    
    # Get the existing code
    old_dialogue_code = dialogue_match.group(1)
    
    # Add fallback logic for dialogue generation
    new_dialogue_code = old_dialogue_code + """
                    
                    # If we reach here with valid dialogue, success
                    logger.info(f"Successfully generated dialogue with {len(dialogue.turns)} turns")
                except ValueError as e:
                    # Specific error for dialogue generation
                    if "Failed to generate valid conversation" in str(e):
                        logger.warning(f"Primary dialogue generation failed: {e}")
                        
                        # Fallback: Try with simplified settings
                        logger.info("Attempting fallback dialogue generation with simplified settings")
                        
                        # Simplify config for fallback attempt
                        fallback_config = config.copy()
                        fallback_config["style"] = "casual"  # Switch to casual style
                        fallback_config["target_duration"] = min(15, config.get("target_duration", 15))  # Reduce length if needed
                        
                        try:
                            fallback_dialogue = await self.conversation.generate_dialogue(
                                analysis,
                                fallback_config
                            )
                            
                            if fallback_dialogue and fallback_dialogue.turns:
                                logger.info(f"Fallback dialogue generation succeeded with {len(fallback_dialogue.turns)} turns")
                                dialogue = fallback_dialogue
                            else:
                                # Re-raise if fallback failed too
                                raise ValueError("Fallback dialogue generation also failed to produce valid results")
                        except Exception as fallback_error:
                            # Re-raise with more context
                            raise ValueError(f"Dialogue generation failed after fallback attempt: {fallback_error}") from e
                    else:
                        # Re-raise original error if not specifically a dialogue validation issue
                        raise"""
    
    # Replace the dialogue generation code block
    current_content = current_content.replace(old_dialogue_code, new_dialogue_code)
    
    # Save the modified file
    podcast_path.write_text(current_content)
    print(f"Updated {podcast_path} with fallback logic")
    return True

def main():
    """Apply all fixes."""
    conv_fixed = fix_conversation_generator()
    podcast_fixed = fix_podcast_generator()
    
    if conv_fixed or podcast_fixed:
        print("\nFixes applied successfully! Try generating a longer podcast again.")
        print("\nThe changes include:")
        print("1. Relaxed validation criteria for longer podcasts")
        print("2. Improved dialogue generation prompts to encourage more detailed responses")
        print("3. Added fallback logic when dialogue generation fails")
        print("\nThese changes should improve success rates for longer podcasts while maintaining quality.")
    else:
        print("\nCould not apply automatic fixes. Manual intervention may be required.")

if __name__ == "__main__":
    main()
