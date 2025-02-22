from typing import List, Dict, Any, Optional
from podgen.services.llm import LLMService, LLMProvider, create_llm_service
from podgen.services.llm.base import SYSTEM_PROMPTS
from .content import (
    ContentExtractorService,
    TextChunker,
    TextChunk,
    SemanticAnalyzer
)
from ..storage.document_store import Document, DocumentStore
import logging

logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """Analyzes document content using LLM capabilities."""

    def __init__(
        self,
        doc_store: DocumentStore,
        llm_provider: Optional[LLMProvider] = None,
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.doc_store = doc_store
        self.extractor = ContentExtractorService()

        # Initialize LLM service with provided configuration
        if llm_provider and llm_model:
            self.llm = create_llm_service(
                provider=llm_provider,
                model_name=llm_model,
                api_key=api_key
            )
        else:
            self.llm = LLMService()

        self.text_chunker = TextChunker()
        self.semantic_analyzer = SemanticAnalyzer(self.llm)

    async def analyze_documents(self, doc_ids: List[int]) -> Dict[str, Any]:
        """Analyze multiple documents using LLM for deep understanding."""
        documents = []
        all_content = []
        
        # First, load all documents
        for doc_id in doc_ids:
            doc = self.doc_store.get_document(doc_id)
            if doc:
                content = await self._load_document_content(doc)
                if content:
                    all_content.append(content)
                    documents.append({
                        'id': doc_id,
                        'content': content,
                        'metadata': doc.metadata
                    })

        if not documents:
            raise ValueError("No valid documents to analyze")

        try:
            # Check if using o1 model
            is_o1_model = hasattr(self.llm, 'model') and str(self.llm.model).startswith('o1')
            
            # Create a focused analysis prompt based on model
            if is_o1_model:
                # Simpler prompt for o1 models
                analysis_prompt = f"""Analyze this content and create a structured analysis. Include these key elements:

1. List exactly 3 main topics covered in the content
2. For each topic, provide at least 2 key points with supporting details
3. List any technical terms that need explanation
4. Suggest a discussion structure with clear segments

Content to analyze:
{all_content[0][:2000]}

Format your response exactly like this:

Main Topics:
1. [First topic]
2. [Second topic]
3. [Third topic]

Key Points:
- [First point from topic 1]: [Supporting detail]
- [Second point from topic 1]: [Supporting detail]
[Continue for other topics]

Technical Terms:
- [Term 1]: [Simple explanation]
- [Term 2]: [Simple explanation]

Discussion Structure:
1. Opening
- Cover [specific topics]
- Focus on [key points]

2. Main Discussion
- Explore [specific topics]
- Highlight [key points]

3. Conclusion
- Summarize [main points]
- Connect [related elements]"""
            else:
                # Original JSON prompt for other models
                analysis_prompt = f"""Analyze this content for a podcast discussion. Return a JSON object with specific information structured exactly as shown below.

CONTENT TO ANALYZE:
{all_content[0][:3000]}

REQUIRED JSON STRUCTURE:
{{
    "main_topics": [
        "First main topic",
        "Second main topic",
        "Third main topic"
    ],
    "key_points": [
        {{
            "point": "First specific point from the content",
            "context": "Direct relevant quote or context",
            "importance": "Clear explanation of why this matters"
        }},
        {{
            "point": "Second specific point",
            "context": "Supporting quote or context",
            "importance": "Why this is significant"
        }}
    ],
    "technical_details": [
        {{
            "term": "Technical term or concept",
            "explanation": "Clear, conversational explanation"
        }}
    ],
    "suggested_structure": [
        {{
            "segment": "Opening",
            "topics": ["Topic 1", "Topic 2"],
            "key_details": ["Important detail 1", "Important detail 2"]
        }},
        {{
            "segment": "Main Discussion",
            "topics": ["Topic 3", "Topic 4"],
            "key_details": ["Detail 3", "Detail 4"]
        }}
    ]
}}"""

            # Get analysis from LLM
            if is_o1_model:
                # Handle text response for o1 models
                response = await self.llm.generate_text(
                    prompt=analysis_prompt,
                    system_prompt="You are an expert content analyzer creating podcast outlines."
                )
                
                # Parse the text response into our required structure
                analysis = self._parse_text_analysis(response)
            else:
                # Use JSON response for other models
                analysis = await self.llm.generate_json(
                    prompt=analysis_prompt,
                    system_prompt="You are an expert content analyzer specializing in creating podcast discussion outlines. Generate only valid JSON data following the exact structure requested."
                )

            # Validate and normalize the analysis
            if not analysis:
                raise ValueError("No analysis produced")
                
            # Ensure we have required fields with minimum content
            if 'main_topics' not in analysis or not isinstance(analysis['main_topics'], list):
                analysis['main_topics'] = self._extract_topics_from_content(all_content[0])
            
            if len(analysis.get('main_topics', [])) < 3:
                # Add generic topics if needed
                generic_topics = ["Document Overview", "Key Concepts", "Practical Applications"]
                analysis['main_topics'].extend(generic_topics[len(analysis['main_topics']):3])
                
            if 'key_points' not in analysis or not isinstance(analysis['key_points'], list):
                analysis['key_points'] = [
                    {
                        "point": f"Discussion of {topic}",
                        "context": "From document analysis",
                        "importance": "Core concept from the content"
                    }
                    for topic in analysis['main_topics'][:3]
                ]

            # Add document info
            analysis['document_info'] = [{
                'id': doc['id'],
                'title': doc['metadata'].get('title', f"Document {doc['id']}"),
                'content_preview': doc['content'][:200] if doc['content'] else None
            } for doc in documents]

            # Add system information
            analysis['llm_provider'] = self.llm.provider_name() if hasattr(self.llm, 'provider_name') else str(type(self.llm).__name__)
            analysis['llm_model'] = self.llm.model if hasattr(self.llm, 'model') else "default"

            return analysis

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise

    def _parse_text_analysis(self, text: str) -> Dict[str, Any]:
        """Parse text-based analysis into structured format."""
        analysis = {
            'main_topics': [],
            'key_points': [],
            'technical_details': [],
            'suggested_structure': []
        }
        
        current_section = None
        current_segment = None
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Detect sections
            lower_line = line.lower()
            if 'main topics:' in lower_line:
                current_section = 'main_topics'
            elif 'key points:' in lower_line:
                current_section = 'key_points'
            elif 'technical terms:' in lower_line:
                current_section = 'technical_details'
            elif 'discussion structure:' in lower_line:
                current_section = 'structure'
            elif line[0].isdigit() and '.' in line[:3]:
                # Numbered point
                content = line[line.find('.')+1:].strip()
                if current_section == 'main_topics':
                    analysis['main_topics'].append(content)
                elif current_section == 'structure':
                    current_segment = {
                        'segment': content,
                        'topics': [],
                        'key_details': []
                    }
                    analysis['suggested_structure'].append(current_segment)
            elif line.startswith('-'):
                # Bullet point
                content = line[1:].strip()
                if current_section == 'key_points':
                    parts = content.split(':', 1)
                    if len(parts) == 2:
                        analysis['key_points'].append({
                            'point': parts[0].strip(),
                            'context': parts[1].strip(),
                            'importance': "Key point from content"
                        })
                elif current_section == 'technical_details':
                    parts = content.split(':', 1)
                    if len(parts) == 2:
                        analysis['technical_details'].append({
                            'term': parts[0].strip(),
                            'explanation': parts[1].strip()
                        })
                elif current_segment is not None:
                    current_segment['key_details'].append(content)
        
        return analysis

    def _extract_topics_from_content(self, content: str) -> List[str]:
        """Extract main topics from content if analysis fails."""
        # Simple topic extraction based on content structure
        paragraphs = content.split('\n\n')
        topics = []
        
        for para in paragraphs[:3]:  # Look at first few paragraphs
            # Extract first sentence from paragraph
            first_sentence = para.split('.')[0].strip()
            if len(first_sentence) > 10:  # Reasonable sentence length
                topics.append(first_sentence[:50] + "..." if len(first_sentence) > 50 else first_sentence)
        
        # Ensure we have at least 3 topics
        while len(topics) < 3:
            topics.append(f"Topic {len(topics) + 1}")
        
        return topics

    async def _load_document_content(self, doc: Document) -> Optional[str]:
        """Load and preprocess document content."""
        result = await self.extractor.extract_content(doc.source)
        if result['error']:
            logger.error(f"Failed to extract content from {doc.source}: {result['error']}")
            return None
        return result['content']

    async def generate_supplementary_content(
        self,
        topics: List[str],
        key_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate additional context and insights using LLM.

        Args:
            topics: Main topics from initial analysis
            key_points: Key points from initial analysis

        Returns:
            Additional insights and context
        """
        try:
            return await self.llm.generate_follow_up(
                [],  # No dialogue context needed
                topics[0],  # Use first topic as main focus
                {"name": "Analyst", "style": "Academic expert"}
            )
        except Exception as e:
            logger.error(f"Supplementary content generation failed: {e}")
            return {}

