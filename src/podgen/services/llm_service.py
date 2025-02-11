import json
from typing import List, Optional
import logging
from openai import OpenAI
from ..models.dialogue import DialogueTurn, Dialogue
from ..models.conversation_config import ConversationConfig
from .llm_prompts import PromptBuilder

logger = logging.getLogger(__name__)

class LLMService:
    """Handles interaction with the LLM for conversation generation."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.prompt_builder = PromptBuilder()
    
    def generate_conversation(
        self,
        topic: str,
        config: ConversationConfig,
        max_retries: int = 3
    ) -> Dialogue:
        """
        Generate a conversation about the given topic.
        
        Args:
            topic: The main topic for discussion
            config: Configuration for the conversation
            max_retries: Maximum number of retry attempts
            
        Returns:
            A complete dialogue
        """
        system_prompt = self.prompt_builder.build_system_prompt(config)
        user_prompt = self.prompt_builder.build_user_prompt(topic)
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                
                # Parse the response
                try:
                    content = json.loads(response.choices[0].message.content)
                except json.JSONDecodeError:
                    # If response isn't valid JSON, try to extract dialogue another way
                    raw_content = response.choices[0].message.content
                    # Create a simple dialogue with one speaker
                    content = {
                        "dialogue": [
                            {
                                "speaker": config.speakers[0].name,
                                "content": raw_content
                            }
                        ]
                    }
                
                turns = []
                
                for turn in content.get("dialogue", []):
                    # Find the corresponding speaker configuration
                    speaker = next(
                        (s for s in config.speakers if s.name == turn["speaker"]),
                        None
                    )
                    if not speaker:
                        logger.warning(f"Unknown speaker {turn['speaker']}")
                        continue
                        
                    turns.append(DialogueTurn(
                        speaker=speaker,
                        content=turn["content"]
                    ))
                
                if not turns:
                    # If no valid turns were created, create one with the first speaker
                    turns.append(DialogueTurn(
                        speaker=config.speakers[0],
                        content=response.choices[0].message.content
                    ))
                
                return Dialogue(turns=turns)
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                
        raise RuntimeError("Failed to generate conversation after max retries")

