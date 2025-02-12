from typing import Dict, Any, List, Type
import logging
from pathlib import Path
from .extractors import (
    ContentExtractor, TextExtractor, PDFExtractor, 
    DocxExtractor, WebExtractor
)

logger = logging.getLogger(__name__)

class ContentExtractorService:
    """Service for extracting content from various sources."""
    
    def __init__(self):
        self.extractors: List[ContentExtractor] = [
            TextExtractor(),
            PDFExtractor(),
            DocxExtractor(),
            WebExtractor()
        ]
    
    async def extract_content(self, source: str) -> Dict[str, Any]:
        """
        Extract content and metadata from a source.
        
        Args:
            source: File path or URL
            
        Returns:
            Dictionary containing:
            - content: Extracted text content
            - metadata: Source metadata
            - error: Error message if extraction failed
        """
        metadata = {}
        
        # Find suitable extractor
        extractor = next(
            (ext for ext in self.extractors if ext.supports(source)),
            None
        )
        
        if not extractor:
            return {
                'content': None,
                'metadata': metadata,
                'error': f'No suitable extractor found for {source}'
            }
        
        try:
            content = await extractor.extract(source, metadata)
            
            if content is None:
                return {
                    'content': None,
                    'metadata': metadata,
                    'error': f'Failed to extract content from {source}'
                }
            
            return {
                'content': content,
                'metadata': metadata,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error extracting content from {source}: {e}")
            return {
                'content': None,
                'metadata': metadata,
                'error': str(e)
            }

