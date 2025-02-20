from typing import List
from podgen.models.conversation_style import ConversationStyle, SpeakerPersonality
from podgen.models.conversation_config import ConversationConfig

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
        
        # Format key points
        points_text = []
        for point in key_points:
            point_text = f"- {point.get('point', '')}"
            if point.get('details'):
                point_text += f"\n  Details: {point['details']}"
            points_text.append(point_text)
        
        # Format speakers
        speakers_text = [f"- {s.name}: {s.style}" for s in speakers]
        
        return f'''Create a detailed {style} conversation for a {target_duration}-minute podcast segment.

CONVERSATION REQUIREMENTS:
1. Length: Approximately {target_words} words total ({target_duration} minutes)
2. Speaking Turns: At least {min_turns} distinct turns
3. Depth: Each turn should be 40-60 words for natural flow
4. Style: {style} tone throughout

CONTENT STRUCTURE:
The conversation must cover these topics and points:
Topics: {", ".join(topics)}

Key Points:
{chr(10).join(points_text)}

SPEAKER ROLES & INTERACTION:
{chr(10).join(speakers_text)}

REQUIRED ELEMENTS:
Introduction (15% of time):
- Warm welcome and topic introduction
- Speaker introductions with expertise context
- Overview of what will be discussed

Main Discussion (70% of time):
- Thorough exploration of each key point
- Real examples and specific details
- Natural transitions between topics
- Interactive discussion and follow-up questions

Conclusion (15% of time):
- Summary of key insights
- Final thoughts from each speaker
- Clear wrap-up

Format the response as JSON:
{
  "dialogue": [
    {"speaker": "SpeakerName", "content": "Natural conversation content"}
  ]
}

Note: Each turn should be substantial and meaningful, avoiding brief exchanges.'''
    