from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass
import tiktoken

@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    content: str
    start_idx: int
    end_idx: int
    metadata: Dict[str, Any]

class TextChunker:
    """Intelligently chunks text while preserving context and structure."""
    
    def __init__(self, model: str = "gpt-4"):
        self.encoder = tiktoken.encoding_for_model(model)
        self.max_tokens = 4000  # Conservative limit for context window
        
    def chunk_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[TextChunk]:
        """
        Split document into semantic chunks respecting natural boundaries.
        
        Args:
            text: Document text to chunk
            metadata: Optional metadata to attach to chunks
            
        Returns:
            List of TextChunk objects
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        # Split into paragraphs first
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            # Count tokens in paragraph
            para_tokens = len(self.encoder.encode(para))
            
            if current_tokens + para_tokens > self.max_tokens:
                # Create new chunk if adding paragraph would exceed limit
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    start_idx = text.index(current_chunk[0])
                    end_idx = start_idx + len(chunk_text)
                    
                    chunks.append(TextChunk(
                        content=chunk_text,
                        start_idx=start_idx,
                        end_idx=end_idx,
                        metadata=metadata or {}
                    ))
                    
                    current_chunk = []
                    current_tokens = 0
                
                # Handle paragraphs that are too long on their own
                if para_tokens > self.max_tokens:
                    # Split into sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    current_sentence_chunk = []
                    current_sentence_tokens = 0
                    
                    for sentence in sentences:
                        sentence_tokens = len(self.encoder.encode(sentence))
                        
                        if current_sentence_tokens + sentence_tokens > self.max_tokens:
                            # Save current sentence chunk
                            if current_sentence_chunk:
                                sentence_text = ' '.join(current_sentence_chunk)
                                start_idx = text.index(sentence_text)
                                end_idx = start_idx + len(sentence_text)
                                
                                chunks.append(TextChunk(
                                    content=sentence_text,
                                    start_idx=start_idx,
                                    end_idx=end_idx,
                                    metadata=metadata or {}
                                ))
                                
                                current_sentence_chunk = []
                                current_sentence_tokens = 0
                        
                        current_sentence_chunk.append(sentence)
                        current_sentence_tokens += sentence_tokens
                    
                    # Add any remaining sentences
                    if current_sentence_chunk:
                        sentence_text = ' '.join(current_sentence_chunk)
                        start_idx = text.index(sentence_text)
                        end_idx = start_idx + len(sentence_text)
                        
                        chunks.append(TextChunk(
                            content=sentence_text,
                            start_idx=start_idx,
                            end_idx=end_idx,
                            metadata=metadata or {}
                        ))
                else:
                    current_chunk.append(para)
                    current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            start_idx = text.index(current_chunk[0])
            end_idx = start_idx + len(chunk_text)
            
            chunks.append(TextChunk(
                content=chunk_text,
                start_idx=start_idx,
                end_idx=end_idx,
                metadata=metadata or {}
            ))
        
        return chunks

    def get_overlap_text(self, chunk1: TextChunk, chunk2: TextChunk, text: str) -> str:
        """Get text between two chunks to maintain context."""
        if chunk2.start_idx > chunk1.end_idx:
            return text[chunk1.end_idx:chunk2.start_idx]
        return ""

