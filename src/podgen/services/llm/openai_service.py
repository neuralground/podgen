import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from .base import LLMService
from .response_parser import parse_json_response

logger = logging.getLogger(__name__)

class OpenAIService(LLMService):
    """LLM service using OpenAI API."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        # Default max tokens for different model types
        self.default_max_tokens = {
            # GPT-4 models
            "gpt-4": 4096,
            "gpt-4-turbo": 4096,
            "gpt-4o": 4096,
            "gpt-4o-mini": 2048,  # More conservative for mini variant
            
            # GPT-3.5 models
            "gpt-3.5-turbo": 4096,
            
            # O1 models
            "o1": 2048,
            "o1-mini": 1024  # Conservative default for mini variant
        }
    
    def _get_max_tokens(self, requested_max: Optional[int] = None) -> int:
        """Get appropriate max_tokens value based on model and request."""
        # If explicitly requested, use that value
        if requested_max is not None:
            return requested_max
            
        # For o1 and gpt-4o models, always provide a max_tokens value
        if self.model.startswith('o1-') or self.model.startswith('gpt-4o'):
            model_base = 'o1-mini' if self.model.startswith('o1-') else 'gpt-4o-mini'
            return self.default_max_tokens.get(self.model, self.default_max_tokens[model_base])
            
        # For other models, let the API use its defaults
        return self.default_max_tokens.get(self.model, None)
    
    def _supports_system_messages(self) -> bool:
        """Check if the model supports system messages."""
        # O1 models and some others don't support system messages
        return not (self.model.startswith('o1-') or self.model.startswith('o1'))

    def _get_token_param_name(self) -> str:
        """Get the correct token limit parameter name for the model."""
        if self.model.startswith('o1-') or self.model.startswith('o1'):
            return 'max_completion_tokens'
        return 'max_tokens'

    def _supports_temperature(self) -> bool:
        """Check if the model supports temperature adjustment."""
        return not (self.model.startswith('o1-') or self.model.startswith('o1'))

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        try:
            # Build messages based on model capabilities
            if system_prompt and not self._supports_system_messages():
                # Prepend system prompt to user prompt for models that don't support system messages
                full_prompt = f"{system_prompt}\n\n{prompt}"
                messages = [{"role": "user", "content": full_prompt}]
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
            
            # Build API parameters
            params = {
                "model": self.model,
                "messages": messages,
            }
            
            # Add temperature only if supported
            if self._supports_temperature() and temperature != 1.0:
                params["temperature"] = temperature
            
            # Add token limit with correct parameter name
            token_limit = self._get_max_tokens(max_tokens)
            if token_limit is not None:
                token_param = self._get_token_param_name()
                params[token_param] = token_limit
            
            # Make the API call
            response = self.client.chat.completions.create(**params)
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        if not "Format your response as JSON" in prompt:
            prompt += "\n\nImportant: Format your entire response as valid JSON."
        
        if system_prompt:
            system_prompt += " Always format responses as valid JSON."
        
        response = await self.generate_text(prompt, system_prompt, temperature)
        return parse_json_response(response)

    async def generate_dialogue(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> List[Dict[str, str]]:
        """Generate dialogue turns from prompt."""
        try:
            # Adjust prompt based on model capabilities
            if self.model.startswith('o1'):
                # Simplified formatting for o1 models
                formatted_prompt = f"""Generate a conversation between exactly these two speakers:
Sam and Michael.

Make it a natural dialogue about the following topic:
{prompt}

Remember:
1. ALWAYS start each line with either "Sam:" or "Michael:"
2. Make each response at least 3-4 full sentences
3. Stay focused on the topic
4. Keep the conversation flowing naturally

Example format:
Sam: [First response about the topic, at least 3-4 sentences]
Michael: [Response to Sam's point, at least 3-4 sentences]
Sam: [Building on Michael's response, at least 3-4 sentences]

Begin the conversation now:"""
            else:
                # Standard JSON format for other models
                formatted_prompt = prompt
                if not '"dialogue"' in formatted_prompt:
                    formatted_prompt += '\n\nFormat your response as JSON with "dialogue" array.'

            # Generate response
            logger.info(f"Generating dialogue with model: {self.model}")
            response = await self.generate_text(formatted_prompt, system_prompt, temperature)
            
            logger.info(f"Raw response from {self.model}:\n{response}")
            
            # Parse response
            dialogue_turns = []
            try:
                if self.model.startswith('o1'):
                    # Parse text format for o1 models
                    current_speaker = None
                    current_content = []
                    
                    for line in response.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Check for speaker prefix
                        if line.startswith('Sam:') or line.startswith('Michael:'):
                            # Save previous turn if exists
                            if current_speaker and current_content:
                                dialogue_turns.append({
                                    'speaker': current_speaker,
                                    'content': ' '.join(current_content).strip()
                                })
                            
                            # Start new turn
                            split_idx = line.find(':')
                            current_speaker = line[:split_idx].strip()
                            current_content = [line[split_idx + 1:].strip()]
                        elif current_speaker and line:
                            current_content.append(line)
                    
                    # Add final turn
                    if current_speaker and current_content:
                        dialogue_turns.append({
                            'speaker': current_speaker,
                            'content': ' '.join(current_content).strip()
                        })
                    
                    logger.info(f"Extracted {len(dialogue_turns)} turns from text format")
                else:
                    # Parse JSON format for other models
                    data = parse_json_response(response)
                    if isinstance(data, dict) and 'dialogue' in data:
                        dialogue_turns = data['dialogue']
                        logger.info(f"Extracted {len(dialogue_turns)} turns from JSON")
                
                # Log parsed turns
                for i, turn in enumerate(dialogue_turns):
                    logger.info(f"Turn {i + 1}:")
                    logger.info(f"  Speaker: {turn.get('speaker', 'Unknown')}")
                    logger.info(f"  Content length: {len(turn.get('content', '').split())} words")
                    logger.info(f"  Content: {turn.get('content', '')[:100]}...")
                
                return dialogue_turns
                
            except Exception as e:
                logger.error(f"Response parsing failed: {str(e)}")
                logger.error(f"Response content:\n{response}")
                return []
            
        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            logger.error(f"Response content: {response if 'response' in locals() else 'No response'}")
            return []
