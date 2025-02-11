from typing import List
from ..models.conversation_style import ConversationStyle, SpeakerPersonality
from ..models.conversation_config import ConversationConfig

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
        
        json_example = '''
{
  "dialogue": [
    {
      "speaker": "Host",
      "content": "Welcome to our discussion..."
    },
    {
      "speaker": "Guest",
      "content": "Thank you for having me..."
    }
  ]
}
'''

        return f"""Generate a natural conversation between {config.num_speakers} speakers discussing the provided topic.

Conversation style: {style_prompts[config.style]}

Speakers and their characteristics:
{speakers_desc}

Additional parameters:
- Topic focus: {topic_focus}
- Interaction: {interaction}

You must format your response as a JSON object with a "dialogue" array. Each item in the dialogue array should have a "speaker" and "content" field. Here's the exact format to use:
{json_example}

Keep the conversation natural and engaging while respecting each speaker's personality."""

    @staticmethod
    def build_user_prompt(topic: str) -> str:
        """Build the user prompt for a given topic."""
        return f"""Generate a conversation discussing the following topic:

{topic}

Remember to:
1. Progress naturally from introduction through development to conclusion
2. Maintain appropriate roles for each speaker
3. Include natural transitions and interactions
4. Cover key aspects of the topic thoroughly
5. Keep it authentic rather than scripted
6. Format the output as JSON with a "dialogue" array"""

