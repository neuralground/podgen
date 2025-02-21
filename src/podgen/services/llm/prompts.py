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
        speakers: List[SpeakerPersonality],
        topics: List[str],
        key_points: List[dict]
    ) -> str:
        """Build the dialogue generation prompt."""
        # Calculate target metrics
        target_words = target_duration * 150  # 150 words per minute
        min_turns = max(10, target_duration * 2)  # At least 2 turns per minute
        words_per_turn = target_words // min_turns
        
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
        
        # Build example turns
        example_turns = []
        for s in speakers:
            example_turns.append({
                "speaker": s.name,
                "content": f"As we explore {topics[0]}, I want to emphasize several crucial points. First, we need to consider the implications carefully. This requires thoughtful analysis and detailed discussion, especially when we look at {key_points[0].get('point', 'our main topic')}. Let me explain why this matters..."
            })

        example_json = json.dumps({"dialogue": example_turns}, indent=2)
        
        return f"""Generate a detailed {style} conversation for a {target_duration}-minute podcast segment. This is a professional podcast requiring substantial, in-depth discussion.

STRICT LENGTH REQUIREMENTS:
1. Total Length: {target_words} words ({target_duration} minutes)
2. Minimum Turns: {min_turns} speaking turns
3. Turn Length: EACH turn MUST be {words_per_turn-20}-{words_per_turn+20} words
   - No short responses or brief acknowledgments
   - Each turn must contribute substantial content
   - Include specific details and examples
   - Develop ideas fully within each turn

CONTENT REQUIREMENTS:
Main Topics: {', '.join(topics)}

Key Points to Cover:
{chr(10).join(points_text)}

SPEAKER PROFILES AND STYLES:
{chr(10).join(speakers_text)}

CONVERSATION STRUCTURE:
1. Opening Segment (15%):
   - Thorough welcome and context setting
   - Detailed speaker introductions
   - Clear agenda for the discussion

2. Main Discussion (70%):
   - Deep exploration of each key point
   - Real-world examples and applications
   - Detailed analysis and insights
   - Natural but substantial transitions
   - Build on previous points
   - Each speaker must demonstrate expertise

3. Closing Segment (15%):
   - Comprehensive summary
   - Key takeaways from each speaker
   - Forward-looking conclusions

IMPORTANT DIALOGUE RULES:
1. NO brief exchanges or short responses
2. Each turn must be self-contained and substantial
3. Maintain natural conversation flow while being detailed
4. Include specific examples and evidence
5. Connect points across the conversation
6. Stay focused on the topics
7. Demonstrate speaker expertise

FORMAT YOUR RESPONSE EXACTLY LIKE THIS EXAMPLE:
{example_json}

Each turn MUST follow these length and format requirements. Responses that are too short or lack substance will be rejected."""