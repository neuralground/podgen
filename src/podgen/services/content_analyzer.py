from typing import List, Dict, Any, Optional
import logging
from .content import (
    ContentExtractorService,
    TextChunker,
    TextChunk,
    SemanticAnalyzer
)
from ..storage.document_store import Document, DocumentStore
from .llm_service import LLMService

logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """Analyzes document content using LLM capabilities."""

    def __init__(self, doc_store: DocumentStore):
        self.doc_store = doc_store
        self.extractor = ContentExtractorService()
        self.llm = LLMService()
        self.text_chunker = TextChunker()
        self.semantic_analyzer = SemanticAnalyzer(self.llm)

    async def analyze_documents(self, doc_ids: List[int]) -> Dict[str, Any]:
        """
        Analyze multiple documents using LLM for deep understanding.

        Args:
            doc_ids: List of document IDs to analyze

        Returns:
            Rich analysis including topics, insights, and conversation structure
        """
        # Collect and extract content from all documents
        documents = []
        chunks = []

        for doc_id in doc_ids:
            doc = self.doc_store.get_document(doc_id)
            if doc:
                content = await self._load_document_content(doc)
                if content:
                    # Create chunks from the document
                    doc_chunks = self.text_chunker.chunk_document(
                        content,
                        metadata={'doc_id': doc_id}
                    )
                    chunks.extend(doc_chunks)

                    documents.append({
                        'id': doc_id,
                        'content': content,
                        'metadata': doc.metadata
                    })

        if not documents:
            raise ValueError("No valid documents to analyze")

        # Compute embeddings for all chunks
        await self.semantic_analyzer.compute_chunk_embeddings(chunks)

        # Find relationships between chunks
        relationships = self.semantic_analyzer.analyze_chunk_relationships(chunks)

        # Perform LLM analysis
        try:
            analysis = await self.llm.analyze_content(documents)

            # Enhance analysis with chunk relationships
            analysis['chunk_relationships'] = relationships

            # Add document metadata
            analysis['document_info'] = [
                {
                    'id': doc['id'],
                    'title': doc['metadata'].get('title', f"Document {doc['id']}"),
                    'type': doc['metadata'].get('type', 'unknown'),
                    'length': len(doc['content'])
                }
                for doc in documents
            ]

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

