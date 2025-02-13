from typing import List, Dict, Any, Optional, Union
import json
import logging
import re
from openai import OpenAI
from ..config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """Enhanced LLM service for content analysis and dialogue generation."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.default_llm_model
    
    async def _call_api(self, prompt: str, retries: int = 2) -> str:
        """Make an API call to the LLM with retries."""
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                # Add explicit JSON instruction if not present
                if "Format your response as" not in prompt:
                    prompt += "\n\nImportant: Format your entire response as valid JSON."
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert content analyst and dialogue writer. Always format your responses as valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=settings.max_tokens
                )
                return response.choices[0].message.content
                
            except Exception as e:
                last_error = e
                logger.warning(f"API call attempt {attempt + 1} failed: {e}")
                continue
                
        raise last_error if last_error else RuntimeError("API call failed")
    
    def _extract_json_from_response(self, response: str) -> Union[Dict, List]:
        """Extract and parse JSON from response, handling common issues."""
        try:
            # First try direct JSON parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to find JSON-like content within markdown or other text
            try:
                # Look for content between triple backticks
                match = re.search(r'```(?:json)?(.*?)```', response, re.DOTALL)
                if match:
                    return json.loads(match.group(1).strip())
                
                # Look for content between curly braces
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                
                # Look for content between square brackets
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                
                raise ValueError("No valid JSON structure found in response")
                
            except Exception as e:
                logger.error(f"Failed to extract JSON: {e}")
                logger.debug(f"Raw response: {response}")
                raise
    
    def _create_fallback_analysis(self, text: str) -> Dict[str, Any]:
        """Create a basic analysis when JSON parsing fails."""
        # Split into sentences and take first few as topics
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        topics = sentences[:2] if sentences else ["General Discussion"]
        
        return {
            "main_topics": topics,
            "key_points": [
                {"point": s, "evidence": "From analysis", "source": "Document 1"}
                for s in sentences[2:5] if s
            ] or [{"point": "General discussion", "evidence": "From analysis", "source": "Document 1"}],
            "quotes": [],
            "relationships": [],
            "suggested_structure": [
                {
                    "segment": "introduction",
                    "duration": 60,
                    "topics": topics[:1],
                    "key_points": [],
                    "format": "welcome"
                },
                {
                    "segment": "main_discussion",
                    "duration": 300,
                    "topics": topics,
                    "key_points": ["Overview of main points"],
                    "format": "discussion"
                },
                {
                    "segment": "conclusion",
                    "duration": 60,
                    "topics": topics,
                    "key_points": ["Summary"],
                    "format": "closing"
                }
            ]
        }
            
    async def analyze_content(self, documents: List[Dict[str, str]]) -> Dict[str, Any]:
        """Analyze document content to extract topics and insights."""
        # Prepare document content for analysis
        docs_text = "\n\n---\n\n".join(
            f"Document {i+1}:\n{doc['content'][:2000]}"
            for i, doc in enumerate(documents)
        )
        
        prompt = f"""Analyze the following documents and extract key information:

{docs_text}

Provide a structured analysis as a JSON object with the following structure:
{{
    "main_topics": ["topic1", "topic2"],
    "key_points": [
        {{"point": "point1", "evidence": "evidence1", "source": "Document X"}}
    ],
    "quotes": [
        {{"text": "quote1", "context": "context1", "source": "Document X"}}
    ],
    "relationships": [
        {{"topic1": "X", "topic2": "Y", "connection": "description"}}
    ],
    "suggested_structure": [
        {{
            "segment": "introduction",
            "duration": 60,
            "topics": ["topic1"],
            "key_points": ["point1"],
            "format": "format_description"
        }}
    ]
}}

Important: Ensure your response is valid JSON."""

        try:
            response = await self._call_api(prompt)
            try:
                return self._extract_json_from_response(response)
            except Exception as e:
                logger.warning(f"Failed to parse analysis JSON: {e}, falling back to basic analysis")
                return self._create_fallback_analysis(response)
                
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            raise

    async def generate_dialogue(
        self,
        prompt: str,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """Generate dialogue based on prompt."""
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = await self._call_api(prompt)
                try:
                    data = self._extract_json_from_response(response)
                    if isinstance(data, dict) and 'dialogue' in data:
                        return data['dialogue']
                    else:
                        logger.warning("Response missing dialogue array")
                        continue
                except Exception as e:
                    logger.warning(f"Failed to parse dialogue JSON: {e}")
                    continue
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Dialogue generation attempt {attempt + 1} failed: {e}")
                continue
                
        # All attempts failed
        if last_error:
            raise last_error
        return []

    async def generate_follow_up(
        self,
        dialogue_context: List[Dict[str, Any]],
        current_topic: str,
        speaker: Dict[str, Any]
    ) -> str:
        """Generate a natural follow-up response in a conversation."""
        context = "\n".join(
            f"{turn['speaker']}: {turn['content']}"
            for turn in dialogue_context[-3:]
        )
        
        prompt = f"""Given this conversation context:

{context}

Generate a natural follow-up response for {speaker['name']} ({speaker['style']}) 
discussing {current_topic}.

Format your response as a simple JSON string:
{{"response": "Your generated response here"}}"""

        try:
            response = await self._call_api(prompt)
            data = self._extract_json_from_response(response)
            return data.get('response', f"Yes, let's discuss {current_topic} further.")
        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}")
            return f"That's an interesting point about {current_topic}."

