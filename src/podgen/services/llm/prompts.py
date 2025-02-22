"""Prompt building and management for LLM services."""

import json
from typing import List, Dict, Any
from ...models.conversation_style import ConversationStyle, SpeakerPersonality
from ...models.conversation_config import ConversationConfig

SYSTEM_PROMPTS = {
    "content_analysis": """You are an expert content analyzer. Extract key information and insights from documents.
Always format your output as valid JSON matching the requested structure.""",
    
    "conversation": """You are an expert dialogue writer creating natural, engaging conversations.
Match the specified style and speaker characteristics.
Always format dialogue as JSON with speaker and content fields.""",
    
    "general": """You are a helpful AI assistant with expertise in many topics.
Provide clear, accurate responses."""
}

class PromptBuilder:
    """Builds prompts for LLM conversation generation."""
    
    @staticmethod
    def build_system_prompt(config: ConversationConfig) -> str:
        """Build the system prompt based on conversation configuration."""
        style_prompts = {
            ConversationStyle.FORMAL: "The conversation should maintain a professional and structured tone.",
            ConversationStyle.CASUAL: "The conversation should feel relaxed and natural.",
            ConversationStyle.FUN: "The conversation should be entertaining and engaging.",
            ConversationStyle.EDUCATIONAL: "The conversation should focus on clear explanation and learning.",
            ConversationStyle.DEBATE: "Speakers should present and discuss different viewpoints.",
            ConversationStyle.INTERVIEW: "Follow an interview format with clear roles."
        }
        
        speakers_desc = "\n".join([
            f"- {s.name}: {s.style} (verbosity: {s.verbosity}, formality: {s.formality})"
            for s in config.speakers
        ])
        
        topic_focus = ('Stay very focused on the main topic' if config.topic_focus > 1.5 
                      else 'Allow natural topic evolution' if config.topic_focus < 0.5 
                      else 'Maintain reasonable topic focus')
        
        interaction = ('Encourage deep interaction between speakers' if config.interaction_depth > 1.5
                      else 'Keep interactions minimal' if config.interaction_depth < 0.5
                      else 'Balance monologue and interaction')

        return f"""Generate a natural conversation between {config.num_speakers} speakers discussing the provided topic.

Conversation style: {style_prompts[config.style]}

Speakers and their characteristics:
{speakers_desc}

Additional parameters:
- Topic focus: {topic_focus}
- Interaction: {interaction}

Format your response as a JSON object with a "dialogue" array. Each item in the dialogue array should have a "speaker" and "content" field."""

    @staticmethod
    def build_dialogue_prompt(
        style: str,
        target_duration: int,
        target_words: int,
        optimal_turns: int,
        speakers: List[SpeakerPersonality],
        topics: List[str],
        key_points: List[dict],
        attempt: int,
        max_attempts: int
    ) -> str:
        """Build the dialogue generation prompt with stronger length emphasis."""
        
        # Format key points
        points_text = []
        for point in key_points:
            point_text = f"- {point.get('point', '')}"
            if point.get('details'):
                point_text += f"\n  Details: {point['details']}"
            points_text.append(point_text)
        
        # Format speakers with more detailed instructions
        speakers_text = []
        for s in speakers:
            style_points = s.style.split(",") if "," in s.style else [s.style]
            style_bullets = "\n    - " + "\n    - ".join(style_points)
            speakers_text.append(f"- {s.name}:{style_bullets}")
        
        # Build example turns with substantial content
        example_turns = []
        
        # Safe access to topics and key points
        default_topic = "the main topic"
        default_point = {"point": "the key aspects", "details": "important considerations"}
        
        topic_to_use = topics[0] if topics else default_topic
        point_to_use = key_points[0] if key_points else default_point
        
        for s in speakers:
            example_turns.append({
                "speaker": s.name,
                "content": f"As we delve into {topic_to_use}, I want to emphasize several crucial aspects that deserve our attention. First, when we consider {point_to_use.get('point', 'the key aspects')}, we need to recognize its broader implications. This isn't just about surface-level understanding - we need to examine how these elements interact and influence real-world outcomes. Let me provide a concrete example that illustrates this point clearly..."
            })

        example_json = json.dumps({"dialogue": example_turns}, indent=2)
        
        # Ensure we have valid topics
        safe_topics = topics if topics else ["Content Overview", "Key Points", "Practical Applications"]
        
        # Format key points safely
        safe_points = []
        if key_points:
            for point in key_points:
                if isinstance(point, dict):
                    point_text = f"- {point.get('point', '')}"
                    if point.get('details'):
                        point_text += f"\n  Details: {point['details']}"
                    safe_points.append(point_text)
        
        if not safe_points:
            safe_points = [
                "- Understand the main concepts\n  Details: Focus on core ideas",
                "- Examine practical applications\n  Details: Real-world examples",
                "- Consider implications\n  Details: Broader context"
            ]
        
        # Build comprehensive prompt
        
        # Build comprehensive prompt
        return f"""Generate an engaging {style} podcast conversation that will take approximately {target_duration} minutes to read aloud.

LENGTH REQUIREMENTS (STRICT):
- Target Word Count: {target_words} words (this is critical)
- This translates to roughly {target_duration} minutes of spoken content
- Required number of substantial speaking turns: {optimal_turns}
- Each turn MUST be 75-150 words minimum
- Previous attempts were too short - this is attempt {attempt} of {max_attempts}
- Short responses or brief acknowledgments will be rejected

CONTENT FOCUS:
Main Topics: {', '.join(topics)}

Key Points to Cover:
{chr(10).join(points_text)}

SPEAKER REQUIREMENTS:
{chr(10).join(speakers_text)}

DIALOGUE STRUCTURE:
1. Opening (15% of total length):
   - Thorough introductions of speakers and topics
   - Clear establishment of context and goals
   - Initial framing of key discussion points
   - Must be at least {int(target_words * 0.15)} words combined

2. Main Discussion (70% of total length):
   - Deep exploration of each major point
   - Detailed examples and real-world applications
   - Substantive back-and-forth between speakers
   - Build complexity through the discussion
   - Must be at least {int(target_words * 0.7)} words combined

3. Conclusion (15% of total length):
   - Comprehensive wrap-up of key points
   - Synthesis of main insights
   - Forward-looking implications
   - Must be at least {int(target_words * 0.15)} words combined

CRITICAL RULES:
1. ABSOLUTELY NO brief exchanges or single-sentence responses
2. Each speaking turn must be self-contained and substantial
3. Include specific examples, data, or evidence in each turn
4. Maintain natural flow while ensuring detailed content
5. Show speaker expertise through depth of responses
6. Connect ideas across the conversation
7. Build complexity as the discussion progresses

Format response as valid JSON with:
{example_json}

LENGTH VALIDATION:
- Target: {target_words} words total
- Minimum turns: {optimal_turns}
- Minimum words per turn: 75
- Previous attempts were too short (attempt {attempt}/{max_attempts})
- Responses not meeting length requirements will be rejected
"""
