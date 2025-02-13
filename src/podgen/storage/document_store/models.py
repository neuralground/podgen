"""Data models for document storage."""

from dataclasses import dataclass
import datetime
from typing import Dict, Any, Optional
from pathlib import Path

@dataclass
class Document:
    """Represents a stored document with cached content"""
    id: int
    source: str  # File path or URL
    doc_type: str  # 'file' or 'url'
    hash: str  # Content hash for deduplication
    local_path: Optional[str]  # Path to local copy of the file
    content: Optional[str]  # Raw content if text-based
    content_hash: Optional[str]  # Hash of the extracted content
    content_date: Optional[datetime.datetime]  # When content was last extracted
    added_date: datetime.datetime  # When document was added
    last_accessed: datetime.datetime  # When document was last accessed
    extracted_text: Optional[str]  # Cached extracted text content
    metadata: Dict[str, Any]  # Flexible metadata storage

    @property
    def local_file(self) -> Optional[Path]:
        """Get the local file path if it exists."""
        if self.local_path:
            path = Path(self.local_path)
            if path.exists():
                return path
        return None

    @property
    def title(self) -> str:
        """Get a display title for the document."""
        if 'title' in self.metadata:
            return self.metadata['title']
        elif self.doc_type == 'file':
            return Path(self.source).name
        else:
            return self.source

    @property
    def has_cached_content(self) -> bool:
        """Check if document has cached extracted content."""
        return bool(self.extracted_text)

    @property
    def needs_refresh(self) -> bool:
        """Check if cached content needs refreshing."""
        if not self.content_date:
            return True
        # Refresh if content is older than 7 days
        age = datetime.datetime.now() - self.content_date
        return age.days > 7

    def __str__(self) -> str:
        """String representation with basic info."""
        return f"{self.title} ({self.doc_type})"

    def __repr__(self) -> str:
        """Detailed representation."""
        return (f"Document(id={self.id}, title='{self.title}', "
                f"type='{self.doc_type}', cached={'Yes' if self.has_cached_content else 'No'})")

