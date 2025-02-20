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
            analysis_prompt = f"""Analyze this document and extract key information for a podcast discussion.
        
DOCUMENT CONTENT:
{all_content[0][:3000]}  # Using first 3000 chars

Provide a structured analysis in this JSON format:
{{
    "main_topics": ["List 3-5 main topics from the document"],
    "key_points": [
        {{"point": "Specific information from the document", 
         "context": "Direct quote or context",
         "importance": "Why this is significant"}}
    ],
    "technical_details": [
        {{"term": "Technical term from document",
         "explanation": "Clear explanation"}}
    ],
    "suggested_structure": [
        {{"segment": "segment_name",
         "topics": ["Specific topics to cover"],
         "key_details": ["Important details to mention"]}}
    ],
    "interesting_elements": [
        {{"element": "Interesting item from document",
         "discussion_angle": "How to present this in conversation"}}
    ]
}}

Ensure all information comes directly from the document content."""

            # Get analysis from LLM
            analysis = await self.llm.generate_json(
                prompt=analysis_prompt,
                system_prompt="You are an expert content analyzer. Extract specific, concrete information directly from the provided document. Do not make up or generalize content."
            )

            # Validate we got meaningful content
            if not analysis or not isinstance(analysis.get('main_topics'), list) or not analysis.get('key_points'):
                raise ValueError("Analysis did not produce required content structure")

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

