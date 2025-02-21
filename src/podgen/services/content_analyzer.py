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
            # Create a focused analysis prompt
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
    ],
    "interesting_elements": [
        {{
            "element": "Interesting fact or concept",
            "discussion_angle": "How to present this in conversation"
        }}
    ]
}}

IMPORTANT RULES:
1. Use ONLY information from the provided content
2. Include at least 3 main topics
3. Include at least 3 key points
4. Format exactly as shown above
5. Do not add any text outside the JSON
6. Ensure all JSON is valid and properly nested"""

            # Get analysis from LLM
            analysis = await self.llm.generate_json(
                prompt=analysis_prompt,
                system_prompt="You are an expert content analyzer specializing in creating podcast discussion outlines. Generate only valid JSON data following the exact structure requested."
            )

            # Validate we got meaningful content
            if not analysis:
                raise ValueError("No analysis produced")
            
            if not isinstance(analysis.get('main_topics'), list) or len(analysis.get('main_topics', [])) < 3:
                raise ValueError("Analysis missing required main topics")
                
            if not isinstance(analysis.get('key_points'), list) or len(analysis.get('key_points', [])) < 3:
                raise ValueError("Analysis missing required key points")

            # Add document info
            analysis['document_info'] = [{
                'id': doc['id'],
                'title': doc['metadata'].get('title', f"Document {doc['id']}"),
                'content_preview': doc['content'][:200] if doc['content'] else None
            } for doc in documents]

            return analysis

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            raise

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

