"""Document store methods for content handling."""

import aiohttp
from pathlib import Path
import datetime
import json
import sqlite3
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DocumentStoreMethods:
    """Methods for document content handling and storage"""
    
    async def _store_remote_file(self, url: str) -> Optional[Path]:
        """Download and store a remote file."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                        
                    content = await response.read()
                    suffix = Path(url).suffix or '.html'
                    dest_path = self.data_dir / f"{self._compute_hash(content)}{suffix}"
                    
                    if not dest_path.exists():
                        dest_path.write_bytes(content)
                    
                    return dest_path
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return None
    
    async def _extract_content(self, source: str, doc_type: str, local_path: Optional[Path] = None) -> Dict[str, Any]:
        """Extract content using appropriate extractor."""
        # Find suitable extractor
        extractor = next(
            (ext for ext in self.extractors if ext.supports(source)),
            None
        )
        
        if not extractor:
            return {
                'content': None,
                'metadata': {},
                'error': f'No suitable extractor found for {source}'
            }
        
        try:
            metadata = {}
            content = await extractor.extract(str(local_path or source), metadata)
            
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
                'metadata': {},
                'error': str(e)
            }
    
    def get_document(self, doc_id: int) -> Optional[Document]:
        """Get a document by ID and update last accessed time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Update last accessed time
            now = datetime.datetime.now()
            c.execute("""
                UPDATE documents 
                SET last_accessed = ? 
                WHERE id = ?
            """, (now, doc_id))
            
            # Get document
            c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = c.fetchone()
            
            if row:
                return Document(
                    id=row['id'],
                    source=row['source'],
                    doc_type=row['doc_type'],
                    hash=row['hash'],
                    local_path=row['local_path'],
                    content=row['content'],
                    content_hash=row['content_hash'],
                    content_date=datetime.datetime.fromisoformat(row['content_date']) if row['content_date'] else None,
                    added_date=datetime.datetime.fromisoformat(row['added_date']),
                    last_accessed=now,
                    extracted_text=row['extracted_text'],
                    metadata=json.loads(row['metadata'])
                )
            
            return None
    
    def get_content(self, doc_id: int) -> Optional[str]:
        """Get cached extracted content for a document."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT extracted_text FROM documents WHERE id = ?", (doc_id,))
            row = c.fetchone()
            return row[0] if row else None
    
    async def refresh_content(self, doc_id: int) -> bool:
        """Re-extract and update cached content."""
        doc = self.get_document(doc_id)
        if not doc:
            return False
            
        result = await self._extract_content(
            doc.source,
            doc.doc_type,
            Path(doc.local_path) if doc.local_path else None
        )
        
        if not result['content']:
            return False
            
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            now = datetime.datetime.now()
            
            c.execute("""
                UPDATE documents
                SET content = ?, content_hash = ?, content_date = ?,
                    extracted_text = ?, metadata = ?
                WHERE id = ?
            """, (
                result['content'],
                self._compute_hash(result['content']),
                now,
                result['content'],  # Store extracted text
                json.dumps(result['metadata']),
                doc_id
            ))
            
            return True

