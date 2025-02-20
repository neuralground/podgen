# src/podgen/services/content/semantic_analyzer.py

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import logging
from podgen.services.llm import LLMService
from .text_chunker import TextChunk

logger = logging.getLogger(__name__)

class SemanticAnalyzer:
    """Handles semantic analysis of text using embeddings."""
    
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self.chunk_embeddings: Dict[str, np.ndarray] = {}
        
    async def compute_chunk_embeddings(
        self,
        chunks: List[TextChunk]
    ) -> Dict[str, np.ndarray]:
        """Compute embeddings for text chunks."""
        embeddings = {}
        
        for chunk in chunks:
            try:
                # Get embedding from OpenAI (synchronous call)
                response = self.llm.client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=chunk.content
                )
                
                # Store embedding
                chunk_id = f"{chunk.start_idx}-{chunk.end_idx}"
                embeddings[chunk_id] = np.array(response.data[0].embedding)
                
            except Exception as e:
                logger.error(f"Failed to compute embedding: {e}")
                continue
        
        self.chunk_embeddings = embeddings
        return embeddings
    
    async def find_related_chunks(
        self,
        query_text: str,
        chunks: List[TextChunk],
        top_k: int = 3
    ) -> List[TextChunk]:
        """Find chunks most semantically related to query text."""
        try:
            # Get query embedding
            response = self.llm.client.embeddings.create(
                model="text-embedding-ada-002",
                input=query_text
            )
            query_embedding = np.array(response.data[0].embedding)
            
            # Calculate similarities
            similarities = []
            for chunk in chunks:
                chunk_id = f"{chunk.start_idx}-{chunk.end_idx}"
                if chunk_id in self.chunk_embeddings:
                    sim = cosine_similarity(
                        query_embedding.reshape(1, -1),
                        self.chunk_embeddings[chunk_id].reshape(1, -1)
                    )[0][0]
                    similarities.append((chunk, sim))
            
            # Sort by similarity and return top k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [chunk for chunk, _ in similarities[:top_k]]
            
        except Exception as e:
            logger.error(f"Failed to find related chunks: {e}")
            return []
    
    def analyze_chunk_relationships(
        self,
        chunks: List[TextChunk]
    ) -> List[Dict[str, Any]]:
        """Analyze relationships between chunks based on semantic similarity."""
        relationships = []
        
        for i, chunk1 in enumerate(chunks):
            chunk1_id = f"{chunk1.start_idx}-{chunk1.end_idx}"
            if chunk1_id not in self.chunk_embeddings:
                continue
                
            for j, chunk2 in enumerate(chunks[i+1:], i+1):
                chunk2_id = f"{chunk2.start_idx}-{chunk2.end_idx}"
                if chunk2_id not in self.chunk_embeddings:
                    continue
                
                # Calculate similarity
                sim = cosine_similarity(
                    self.chunk_embeddings[chunk1_id].reshape(1, -1),
                    self.chunk_embeddings[chunk2_id].reshape(1, -1)
                )[0][0]
                
                if sim > 0.7:  # Only include strong relationships
                    relationships.append({
                        'chunk1_id': chunk1_id,
                        'chunk2_id': chunk2_id,
                        'similarity': float(sim),
                        'type': 'semantic_similarity'
                    })
        
        return relationships
    