"""Document storage implementation with content caching."""

from pathlib import Path
import sqlite3
import hashlib
import datetime
import logging
import urllib.parse
import shutil
import json
import aiohttp
from typing import List, Optional, Dict, Any, Union
from .models import Document
from ...services.content.extractors import (
    ContentExtractor, TextExtractor, PDFExtractor, 
    DocxExtractor, WebExtractor
)

logger = logging.getLogger(__name__)

class DocumentStore:
    """Manages document storage and retrieval with content caching"""

    def __init__(self, db_path: Path):
        """Initialize document storage with database path"""
        self.db_path = db_path
        self.data_dir = db_path.parent / "files"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
        # Initialize extractors
        self.extractors = [
            TextExtractor(),
            PDFExtractor(),
            DocxExtractor(),
            WebExtractor()
        ]

    def _init_db(self):
        """Initialize the database schema"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Create documents table with additional fields
            c.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    local_path TEXT,
                    content TEXT,
                    content_hash TEXT,
                    content_date TIMESTAMP,
                    added_date TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    extracted_text TEXT,  -- Cached extracted content
                    metadata TEXT  -- JSON string for flexible metadata
                )
            """)
            
            # Create indexes
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_hash 
                ON documents(hash)
            """)
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_content_hash 
                ON documents(content_hash)
            """)
            
            conn.commit()
    
    def _compute_hash(self, content: Union[str, bytes]) -> str:
        """Compute SHA-256 hash of content"""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha256(content).hexdigest()
    
    def _store_local_file(self, source_path: Path) -> Path:
        """Store a local file in the data directory."""
        dest_path = self.data_dir / f"{self._compute_hash(source_path.read_bytes())}{source_path.suffix}"
        if not dest_path.exists():
            shutil.copy2(source_path, dest_path)
        return dest_path

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

    async def _insert_document(
        self, 
        cursor,
        source: str,
        doc_type: str,
        doc_hash: str,
        local_path: Optional[str],
        content: Optional[str],
        content_hash: Optional[str],
        extracted_text: Optional[str],
        metadata: Dict,
        timestamp: datetime.datetime
    ) -> Document:
        """Helper method to insert a document into the database."""
        cursor.execute("""
            INSERT INTO documents 
            (source, doc_type, hash, local_path, content, content_hash,
             content_date, added_date, last_accessed, extracted_text, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            source,
            doc_type,
            doc_hash,
            local_path,
            content,
            content_hash,
            timestamp,
            timestamp,
            timestamp,
            extracted_text,
            json.dumps(metadata)
        ))
        
        doc_id = cursor.lastrowid
        
        return Document(
            id=doc_id,
            source=source,
            doc_type=doc_type,
            hash=doc_hash,
            local_path=local_path,
            content=content,
            content_hash=content_hash,
            content_date=timestamp,
            added_date=timestamp,
            last_accessed=timestamp,
            extracted_text=extracted_text,
            metadata=metadata
        )

    async def add_file(self, file_path: Path) -> Document:
        """Add a file to the document store with content caching."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = file_path.read_bytes()
        file_hash = self._compute_hash(content)
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM documents WHERE hash = ?", (file_hash,))
            if c.fetchone():
                raise ValueError(f"File already exists in store: {file_path}")
            
            local_path = self._store_local_file(file_path)
            result = await self._extract_content(str(file_path), 'file', local_path)
            
            now = datetime.datetime.now()
            content_hash = self._compute_hash(result['content']) if result['content'] else None
            
            doc = await self._insert_document(
                c,
                source=str(file_path),
                doc_type='file',
                doc_hash=file_hash,
                local_path=str(local_path),
                content=result['content'],
                content_hash=content_hash,
                extracted_text=result['content'],
                metadata=result['metadata'],
                timestamp=now
            )
            
            conn.commit()
            return doc

    async def add_url(self, url: str) -> Document:
        """Add a URL to the document store with content caching."""
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid URL")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        
        url_hash = self._compute_hash(url)
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM documents WHERE hash = ?", (url_hash,))
            if c.fetchone():
                raise ValueError(f"URL already exists in store: {url}")
            
            local_path = await self._store_remote_file(url)
            result = await self._extract_content(url, 'url', local_path)
            
            now = datetime.datetime.now()
            content_hash = self._compute_hash(result['content']) if result['content'] else None
            
            doc = await self._insert_document(
                c,
                source=url,
                doc_type='url',
                doc_hash=url_hash,
                local_path=str(local_path) if local_path else None,
                content=result['content'],
                content_hash=content_hash,
                extracted_text=result['content'],
                metadata=result['metadata'],
                timestamp=now
            )
            
            conn.commit()
            return doc

    def remove(self, doc_id: int) -> bool:
        """Remove a document and its local files if no longer needed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                c.execute("SELECT local_path FROM documents WHERE id = ?", (doc_id,))
                row = c.fetchone()
                if not row:
                    return False
                
                local_path = row[0]
                c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                
                if local_path:
                    path = Path(local_path)
                    if path.exists():
                        c.execute("SELECT COUNT(*) FROM documents WHERE local_path = ?", (local_path,))
                        if c.fetchone()[0] == 0:
                            try:
                                path.unlink()
                            except Exception as e:
                                logger.warning(f"Failed to remove file {path}: {e}")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to remove document {doc_id}: {e}")
            return False

    def get_document(self, doc_id: int) -> Optional[Document]:
        """Get a document by ID and update last accessed time."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            now = datetime.datetime.now()
            c.execute("""
                UPDATE documents 
                SET last_accessed = ? 
                WHERE id = ?
            """, (now, doc_id))
            
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

    def list_documents(self) -> List[Document]:
        """List all documents in the store"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("""
                SELECT * FROM documents 
                ORDER BY added_date DESC
            """)
            
            return [
                Document(
                    id=row['id'],
                    source=row['source'],
                    doc_type=row['doc_type'],
                    hash=row['hash'],
                    local_path=row['local_path'],
                    content=row['content'],
                    content_hash=row['content_hash'],
                    content_date=datetime.datetime.fromisoformat(row['content_date']) if row['content_date'] else None,
                    added_date=datetime.datetime.fromisoformat(row['added_date']),
                    last_accessed=datetime.datetime.fromisoformat(row['last_accessed']),
                    extracted_text=row['extracted_text'],
                    metadata=json.loads(row['metadata'])
                )
                for row in c.fetchall()
            ]

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
                result['content'],
                json.dumps(result['metadata']),
                doc_id
            ))
            
            return True

