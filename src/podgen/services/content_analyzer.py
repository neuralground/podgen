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
        logger.info(f"Starting document analysis for {len(doc_ids)} documents")
        documents = []
        all_content = []
        
        # First, load all documents
        for doc_id in doc_ids:
            try:
                doc = self.doc_store.get_document(doc_id)
                if doc:
                    logger.info(f"Loading content for document {doc_id}")
                    content = await self._load_document_content(doc)
                    if content:
                        logger.info(f"Loaded {len(content)} chars from document {doc_id}")
                        all_content.append(content)
                        documents.append({
                            'id': doc_id,
                            'content': content,
                            'metadata': doc.metadata
                        })
                    else:
                        logger.warning(f"No content extracted from document {doc_id}")
            except Exception as e:
                logger.error(f"Error loading document {doc_id}: {str(e)}")

        if not documents:
            logger.error("No valid documents to analyze")
            raise ValueError("No valid documents to analyze")

        try:
            # Create a simplified analysis prompt for deepseek-r1
            analysis_prompt = f"""Analyze this content and extract key information. Provide a clear, structured response following exactly this format:

MAIN TOPICS:
- Topic 1
- Topic 2
- Topic 3

KEY POINTS:
- Point 1: Supporting detail
- Point 2: Supporting detail
- Point 3: Supporting detail

TECHNICAL TERMS:
- Term 1: Definition
- Term 2: Definition

DISCUSSION STRUCTURE:
1. Opening (Overview of topics)
2. Main Discussion (Key points to cover)
3. Conclusion (Summary and implications)

Here is the content to analyze:

{all_content[0][:3000]}"""

            logger.info("Sending analysis prompt to LLM")
            logger.debug(f"Prompt length: {len(analysis_prompt)}")
            
            # Generate text response
            response = await self.llm.generate_text(
                prompt=analysis_prompt,
                temperature=0.7
            )
            
            if not response:
                logger.error("Received empty response from LLM")
                raise ValueError("Empty response from LLM")
                
            logger.info(f"Received response of length {len(response)}")
            logger.debug(f"Response preview: {response[:500]}...")
            
            # Parse the structured text response
            analysis = self._parse_text_analysis(response)
            
            # Validate minimum required content
            if not analysis.get('main_topics'):
                logger.error("No main topics found in analysis")
                raise ValueError("No main topics in analysis")
                
            if not analysis.get('key_points'):
                logger.error("No key points found in analysis")
                raise ValueError("No key points in analysis")
            
            # Add document info
            analysis['document_info'] = [{
                'id': doc['id'],
                'title': doc['metadata'].get('title', f"Document {doc['id']}"),
                'content_preview': doc['content'][:200] if doc['content'] else None
            } for doc in documents]

            # Add system information
            analysis['llm_provider'] = self.llm.provider_name() if hasattr(self.llm, 'provider_name') else str(type(self.llm).__name__)
            analysis['llm_model'] = self.llm.model if hasattr(self.llm, 'model') else "default"

            logger.info("Successfully completed content analysis")
            return analysis

        except Exception as e:
            logger.error(f"Content analysis failed: {str(e)}")
            raise

    def _parse_text_analysis(self, text: str) -> Dict[str, Any]:
        """Parse structured text response into analysis dictionary."""
        logger.info("Parsing analysis response")
        
        analysis = {
            'main_topics': [],
            'key_points': [],
            'technical_details': [],
            'suggested_structure': []
        }
        
        try:
            current_section = None
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Detect sections
                line_upper = line.upper()
                if 'MAIN TOPICS:' in line_upper:
                    current_section = 'main_topics'
                    logger.debug("Found MAIN TOPICS section")
                    continue
                elif 'KEY POINTS:' in line_upper:
                    current_section = 'key_points'
                    logger.debug("Found KEY POINTS section")
                    continue
                elif 'TECHNICAL TERMS:' in line_upper:
                    current_section = 'technical_details'
                    logger.debug("Found TECHNICAL TERMS section")
                    continue
                elif 'DISCUSSION STRUCTURE:' in line_upper:
                    current_section = 'structure'
                    logger.debug("Found DISCUSSION STRUCTURE section")
                    continue
                    
                # Skip lines without content
                if not current_section or not line or line.startswith('('):
                    continue
                    
                # Process content based on section
                if line.startswith(('•', '-', '*', '1.', '2.', '3.')):
                    content = line.lstrip('•-*123. ').strip()
                    if not content:
                        continue
                    
                    if current_section == 'main_topics':
                        analysis['main_topics'].append(content)
                        logger.debug(f"Added main topic: {content}")
                        
                    elif current_section == 'key_points':
                        parts = content.split(':', 1)
                        if len(parts) == 2:
                            point = {
                                'point': parts[0].strip(),
                                'context': parts[1].strip(),
                                'importance': "Key discussion point"
                            }
                        else:
                            point = {
                                'point': content,
                                'context': "From document analysis",
                                'importance': "Key discussion point"
                            }
                        analysis['key_points'].append(point)
                        logger.debug(f"Added key point: {point['point']}")
                        
                    elif current_section == 'technical_details':
                        parts = content.split(':', 1)
                        if len(parts) == 2:
                            analysis['technical_details'].append({
                                'term': parts[0].strip(),
                                'explanation': parts[1].strip()
                            })
                            logger.debug(f"Added technical term: {parts[0].strip()}")
                            
                    elif current_section == 'structure':
                        analysis['suggested_structure'].append({
                            'segment': content,
                            'topics': [],
                            'key_details': [content]
                        })
                        logger.debug(f"Added structure segment: {content}")
            
            logger.info(f"Parsed {len(analysis['main_topics'])} topics, {len(analysis['key_points'])} points")
            return analysis
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {str(e)}")
            raise

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

