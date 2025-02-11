"""Data models for document storage."""

from dataclasses import dataclass
import datetime
from typing import Dict, Any

@dataclass
class Document:
    """Represents a stored document"""
    id: int
    source: str  # File path or URL
    doc_type: str  # 'file' or 'url'
    hash: str  # Content hash for deduplication
    added_date: datetime.datetime
    last_accessed: datetime.datetime
    metadata: Dict[str, Any]  # Flexible metadata storage

