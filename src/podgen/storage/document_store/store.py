"""Document storage implementation with content caching."""

from pathlib import Path
import sqlite3
import hashlib
import datetime
import logging
import urllib.parse
import shutil
import json
from typing import List, Optional, Dict, Any, Union
import aiohttp
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
        print(f"DEBUG: Initializing DocumentStore with DB: {db_path}, Files: {self.data_dir}")
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
        print("DEBUG: Initializing document store database")
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Create documents table
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
                    extracted_text TEXT,
                    metadata TEXT
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
            print("DEBUG: Database initialization complete")

    def _compute_hash(self, content: Union[str, bytes]) -> str:
        """Compute SHA-256 hash of content"""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.sha256(content).hexdigest()

    def _store_local_file(self, source_path: Path) -> Path:
        """Store a local file in the data directory."""
        print(f"DEBUG: Storing local file {source_path}")
        dest_path = self.data_dir / f"{self._compute_hash(source_path.read_bytes())}{source_path.suffix}"
        if not dest_path.exists():
            shutil.copy2(source_path, dest_path)
        print(f"DEBUG: File stored at {dest_path}")
        return dest_path

    async def add_file(self, file_path: Path) -> Document:
        """Add a file to the document store with content caching."""
        print(f"DEBUG: Adding file: {file_path}")
        if not file_path.exists():
            print(f"DEBUG: File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            content = file_path.read_bytes()
            file_hash = self._compute_hash(content)
            print(f"DEBUG: File hash: {file_hash}")
            
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM documents WHERE hash = ?", (file_hash,))
                if c.fetchone():
                    print(f"DEBUG: File already exists in store")
                    raise ValueError(f"File already exists in store: {file_path}")
                
                local_path = self._store_local_file(file_path)
                print(f"DEBUG: Stored local file at: {local_path}")
                
                # Extract content
                extractor = next(
                    (ext for ext in self.extractors if ext.supports(str(file_path))),
                    None
                )
                
                if not extractor:
                    raise ValueError(f"No suitable extractor found for {file_path}")
                
                metadata = {}
                print(f"DEBUG: Extracting content using {extractor.__class__.__name__}")
                content = await extractor.extract(str(file_path), metadata)
                
                if content is None:
                    raise ValueError(f"Failed to extract content from {file_path}")
                
                print(f"DEBUG: Content extracted successfully")
                
                now = datetime.datetime.now()
                content_hash = self._compute_hash(content)
                
                # Insert document
                c.execute("""
                    INSERT INTO documents 
                    (source, doc_type, hash, local_path, content, content_hash,
                     content_date, added_date, last_accessed, extracted_text, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(file_path),
                    'file',
                    file_hash,
                    str(local_path),
                    content,
                    content_hash,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                    content,
                    json.dumps(metadata)
                ))
                
                doc_id = c.lastrowid
                print(f"DEBUG: Document inserted with ID: {doc_id}")
                
                doc = Document(
                    id=doc_id,
                    source=str(file_path),
                    doc_type='file',
                    hash=file_hash,
                    local_path=str(local_path),
                    content=content,
                    content_hash=content_hash,
                    content_date=now,
                    added_date=now,
                    last_accessed=now,
                    extracted_text=content,
                    metadata=metadata
                )
                
                conn.commit()
                return doc
                
        except Exception as e:
            print(f"DEBUG: Error adding file: {type(e).__name__}: {str(e)}")
            raise

    async def add_url(self, url: str) -> Document:
        """Add a URL to the document store with content caching."""
        try:
            parsed = urllib.parse.urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError("Invalid URL")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")
        
        try:
            url_hash = self._compute_hash(url)
            
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT id FROM documents WHERE hash = ?", (url_hash,))
                if c.fetchone():
                    raise ValueError(f"URL already exists in store: {url}")
                
                # Download content
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise ValueError(f"Failed to fetch URL: {response.status}")
                        
                        content = await response.read()
                        
                # Store locally
                suffix = Path(url).suffix or '.html'
                local_path = self.data_dir / f"{self._compute_hash(content)}{suffix}"
                local_path.write_bytes(content)
                
                # Extract content
                metadata = {}
                result = await self.extractors[3].extract(url, metadata)  # Use WebExtractor
                
                if not result:
                    raise ValueError(f"Failed to extract content from {url}")
                
                now = datetime.datetime.now()
                content_hash = self._compute_hash(result)
                
                # Insert document
                c.execute("""
                    INSERT INTO documents 
                    (source, doc_type, hash, local_path, content, content_hash,
                     content_date, added_date, last_accessed, extracted_text, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    url,
                    'url',
                    url_hash,
                    str(local_path),
                    result,
                    content_hash,
                    now.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                    result,
                    json.dumps(metadata)
                ))
                
                doc_id = c.lastrowid
                
                doc = Document(
                    id=doc_id,
                    source=url,
                    doc_type='url',
                    hash=url_hash,
                    local_path=str(local_path),
                    content=result,
                    content_hash=content_hash,
                    content_date=now,
                    added_date=now,
                    last_accessed=now,
                    extracted_text=result,
                    metadata=metadata
                )
                
                conn.commit()
                return doc
                
        except Exception as e:
            logger.error(f"Failed to add URL {url}: {e}")
            raise

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
            """, (now.isoformat(), doc_id))
            
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
        print("DEBUG: Listing documents")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("""
                SELECT * FROM documents 
                ORDER BY added_date DESC
            """)
            
            rows = c.fetchall()
            print(f"DEBUG: Found {len(rows)} documents")
            
            docs = []
            for row in rows:
                try:
                    doc = Document(
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
                    docs.append(doc)
                except Exception as e:
                    print(f"DEBUG: Error loading document: {type(e).__name__}: {str(e)}")
                    continue
            
            return docs

    def remove(self, doc_id: int) -> bool:
        """Remove a document and its local files."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Get document info
                c.execute("SELECT local_path FROM documents WHERE id = ?", (doc_id,))
                row = c.fetchone()
                if not row:
                    return False
                
                local_path = row[0]
                
                # Delete from database
                c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                conn.commit()
                
                # Remove local file if no other documents reference it
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

    async def refresh_content(self, doc_id: int) -> bool:
        """Re-extract and update cached content."""
        doc = self.get_document(doc_id)
        if not doc:
            return False
            
        try:
            # Re-extract content
            extractor = next(
                (ext for ext in self.extractors if ext.supports(doc.source)),
                None
            )
            
            if not extractor:
                raise ValueError(f"No suitable extractor found for {doc.source}")
            
            metadata = {}
            content = await extractor.extract(
                str(Path(doc.local_path)) if doc.local_path else doc.source,
                metadata
            )
            
            if not content:
                raise ValueError(f"Failed to extract content from {doc.source}")
            
            # Update document
            now = datetime.datetime.now()
            content_hash = self._compute_hash(content)
            
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    UPDATE documents
                    SET content = ?, content_hash = ?, content_date = ?,
                        extracted_text = ?, metadata = ?
                    WHERE id = ?
                """, (
                    content,
                    content_hash,
                    now.isoformat(),
                    content,
                    json.dumps(metadata),
                    doc_id
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to refresh document {doc_id}: {e}")
            return False

