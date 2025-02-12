import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import datetime
from .models import Conversation, ConversationStatus

logger = logging.getLogger(__name__)

class ConversationStore:
    """Manages storage of generated conversations."""
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize or migrate the database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Check if schema_version table exists
            c.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_version'
            """)
            
            if not c.fetchone():
                # Fresh database, create all tables
                self._create_schema(c)
                c.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self.SCHEMA_VERSION,)
                )
            else:
                # Check current version and migrate if needed
                c.execute("SELECT version FROM schema_version")
                current_version = c.fetchone()[0]
                
                if current_version < self.SCHEMA_VERSION:
                    self._migrate_schema(c, current_version)
                    c.execute(
                        "UPDATE schema_version SET version = ?",
                        (self.SCHEMA_VERSION,)
                    )
            
            conn.commit()
    
    def _create_schema(self, cursor):
        """Create fresh database schema."""
        # Schema version tracking
        cursor.execute("""
            CREATE TABLE schema_version (
                version INTEGER NOT NULL
            )
        """)
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                transcript TEXT,
                audio_path TEXT,
                created_date TIMESTAMP NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL,
                error TEXT,
                metadata TEXT
            )
        """)
    
    def _migrate_schema(self, cursor, from_version: int):
        """
        Migrate database schema from a previous version.
        Handles incremental updates between versions.
        """
        if from_version == 0:
            # Migrating from initial version without status tracking
            
            # Create temporary table with new schema
            cursor.execute("""
                CREATE TABLE conversations_new (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    transcript TEXT,
                    audio_path TEXT,
                    created_date TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL,
                    error TEXT,
                    metadata TEXT
                )
            """)
            
            # Copy existing data with default values for new columns
            cursor.execute("""
                INSERT INTO conversations_new 
                SELECT 
                    id, 
                    title, 
                    transcript, 
                    audio_path, 
                    created_date,
                    CASE 
                        WHEN audio_path IS NOT NULL THEN 'completed'
                        ELSE 'failed'
                    END as status,
                    CASE 
                        WHEN audio_path IS NOT NULL THEN 1.0
                        ELSE 0.0
                    END as progress,
                    NULL as error,
                    metadata
                FROM conversations
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE conversations")
            cursor.execute("ALTER TABLE conversations_new RENAME TO conversations")
    
    def create_pending(
        self,
        title: str,
        metadata: Dict[str, Any] = None
    ) -> Conversation:
        """Create a new pending conversation."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            now = datetime.datetime.now()
            c.execute("""
                INSERT INTO conversations 
                (title, created_date, status, progress, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                title,
                now.isoformat(),
                ConversationStatus.GENERATING.value,
                0.0,
                json.dumps(metadata or {})
            ))
            
            conv_id = c.lastrowid
            conn.commit()
            
            return Conversation(
                id=conv_id,
                title=title,
                transcript=None,
                audio_path=None,
                created_date=now,
                status=ConversationStatus.GENERATING,
                progress=0.0,
                error=None,
                metadata=metadata or {}
            )
    
    def update_progress(
        self,
        conv_id: int,
        progress: float,
        transcript: Optional[str] = None,
        audio_path: Optional[Path] = None
    ) -> None:
        """Update generation progress."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            updates = ["progress = ?"]
            params = [progress]
            
            if transcript is not None:
                updates.append("transcript = ?")
                params.append(transcript)
            
            if audio_path is not None:
                updates.append("audio_path = ?")
                params.append(str(audio_path))
            
            if progress >= 1.0:
                updates.append("status = ?")
                params.append(ConversationStatus.COMPLETED.value)
            
            params.append(conv_id)
            
            c.execute(f"""
                UPDATE conversations 
                SET {", ".join(updates)}
                WHERE id = ?
            """, params)
            
            conn.commit()
    
    def mark_failed(self, conv_id: int, error: str) -> None:
        """Mark conversation as failed."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            c.execute("""
                UPDATE conversations 
                SET status = ?, error = ?
                WHERE id = ?
            """, (ConversationStatus.FAILED.value, error, conv_id))
            
            conn.commit()
    
    def get(self, conv_id: int) -> Optional[Conversation]:
        """Get a conversation by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = c.fetchone()
            
            if row:
                return Conversation(
                    id=row['id'],
                    title=row['title'],
                    transcript=row['transcript'],
                    audio_path=Path(row['audio_path']) if row['audio_path'] else None,
                    created_date=datetime.datetime.fromisoformat(row['created_date']),
                    status=ConversationStatus(row['status']),
                    progress=row['progress'],
                    error=row['error'],
                    metadata=json.loads(row['metadata'])
                )
        return None
    
    def list_all(self) -> List[Conversation]:
        """List all conversations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute("SELECT * FROM conversations ORDER BY created_date DESC")
            
            return [
                Conversation(
                    id=row['id'],
                    title=row['title'],
                    transcript=row['transcript'],
                    audio_path=Path(row['audio_path']) if row['audio_path'] else None,
                    created_date=datetime.datetime.fromisoformat(row['created_date']),
                    status=ConversationStatus(row['status']),
                    progress=row['progress'],
                    error=row['error'],
                    metadata=json.loads(row['metadata'])
                )
                for row in c.fetchall()
            ]
    
    def remove(self, conv_id: int) -> bool:
        """Remove a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            return c.rowcount > 0

