"""Document storage implementation."""

from pathlib import Path
import sqlite3
import hashlib
import datetime
import logging
import urllib.parse
from typing import List, Optional, Dict, Any
from .models import Document

logger = logging.getLogger(__name__)

class DocumentStore:
    """Manages document storage and retrieval"""

    def __init__(self, db_path: Path):
        """Initialize document storage with database path"""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Create documents table
            c.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    added_date TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    metadata TEXT  -- JSON string for flexible metadata
                )
            """)
            
            # Create index on hash for deduplication checks
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_hash 
                ON documents(hash)
            """)
            
            conn.commit()
    
    def _compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of content"""
        return hashlib.sha256(content).hexdigest()
    
    def add_file(self, file_path: Path) -> Document:
        """
        Add a file to the document store
        
        Args:
            file_path: Path to the file to add
            
        Returns:
            Document object representing the stored document
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is already in store
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read file and compute hash
        content = file_path.read_bytes()
        file_hash = self._compute_hash(content)
        
        # Check for duplicates
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM documents WHERE hash = ?", (file_hash,))
            if c.fetchone():
                raise ValueError(f"File already exists in store: {file_path}")
            
            # Store new document
            now = datetime.datetime.now()
            c.execute("""
                INSERT INTO documents 
                (source, doc_type, hash, added_date, last_accessed, metadata)
                VALUES (?, ?, ?, ?, ?, '{}')
            """, (str(file_path), 'file', file_hash, now, now))
            
            doc_id = c.lastrowid
            conn.commit()
            
            return Document(
                id=doc_id,
                source=str(file_path),
                doc_type='file',
                hash=file_hash,
                added_date=now,
                last_accessed=now,
                metadata={}
            )
    
    def add_url(self, url: str) -> Document:
        """
        Add a URL to the document store
        
        Args:
            url: URL to add
            
        Returns:
            Document object representing the stored document
            
        Raises:
            ValueError: If URL is invalid or already in store
        """
        # Basic URL validation
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid URL")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        
        # Use URL as unique identifier
        url_hash = self._compute_hash(url.encode())
        
        # Check for duplicates
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM documents WHERE hash = ?", (url_hash,))
            if c.fetchone():
                raise ValueError(f"URL already exists in store: {url}")
            
            # Store new document
            now = datetime.datetime.now()
            c.execute("""
                INSERT INTO documents 
                (source, doc_type, hash, added_date, last_accessed, metadata)
                VALUES (?, ?, ?, ?, ?, '{}')
            """, (url, 'url', url_hash, now, now))
            
            doc_id = c.lastrowid
            conn.commit()
            
            return Document(
                id=doc_id,
                source=url,
                doc_type='url',
                hash=url_hash,
                added_date=now,
                last_accessed=now,
                metadata={}
            )
    
    def remove(self, doc_id: int) -> bool:
        """
        Remove a document from the store
        
        Returns:
            True if document was removed, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return c.rowcount > 0
    
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
                    added_date=datetime.datetime.fromisoformat(row['added_date']),
                    last_accessed=datetime.datetime.fromisoformat(row['last_accessed']),
                    metadata={}  # TODO: Parse JSON metadata
                )
                for row in c.fetchall()
            ]
    
    def get_document(self, doc_id: int) -> Optional[Document]:
        """Get a specific document by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = c.fetchone()
            
            if row:
                return Document(
                    id=row['id'],
                    source=row['source'],
                    doc_type=row['doc_type'],
                    hash=row['hash'],
                    added_date=datetime.datetime.fromisoformat(row['added_date']),
                    last_accessed=datetime.datetime.fromisoformat(row['last_accessed']),
                    metadata={}  # TODO: Parse JSON metadata
                )

