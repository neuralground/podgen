"""Conversation configuration and prompting."""

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from typing import List, Dict, Any
import datetime

from ..storage.document_store import Document, DocumentStore
from ..models.speaker_profiles import (
    DEFAULT_SPEAKER_PROFILES,
    get_default_speakers,
    get_available_styles,
    get_available_speaker_roles
)

async def prompt_conversation_config(
    console: Console,
    doc_store: DocumentStore,
    documents: List[Document]
) -> Dict[str, Any]:
    """Prompt user for conversation configuration."""
    # Quick analysis of sources for default title
    doc_titles = [doc.metadata.get('title', f'Document {doc.id}') for doc in documents]
    default_title = "Discussion: " + ", ".join(doc_titles[:2])
    if len(doc_titles) > 2:
        default_title += f" and {len(doc_titles)-2} more"
    
    # Get podcast title
    title = Prompt.ask(
        "Enter podcast title",
        default=default_title
    )
    
    # Show available styles
    console.print("\nAvailable conversation styles:")
    styles = get_available_styles()
    for style in styles:
        speakers = get_default_speakers(style)
        console.print(f"  {style}: {', '.join(s.name for s in speakers)}")
    
    # Get conversation style
    style = Prompt.ask(
        "\nChoose conversation style",
        choices=styles,
        default="casual"
    )
    
    # Get speakers
    default_speakers = get_default_speakers(style)
    speaker_roles = []
    
    console.print("\nAvailable speaker roles:")
    roles = get_available_speaker_roles()
    role_table = Table("Role", "Name", "Style")
    for role in roles:
        speaker = DEFAULT_SPEAKER_PROFILES[role]
        role_table.add_row(role, speaker.name, speaker.style)
    console.print(role_table)
    
    for i, default_speaker in enumerate(default_speakers):
        role_name = ["Host", "Co-host", "Guest"][i] if i < 3 else f"Speaker {i+1}"
        role = Prompt.ask(
            f"\nChoose {role_name} role",
            choices=roles,
            default=next(
                role for role, speaker in DEFAULT_SPEAKER_PROFILES.items()
                if speaker.name == default_speaker.name
            )
        )
        speaker_roles.append(role)
    
    # Get target duration
    duration = IntPrompt.ask(
        "\nTarget podcast duration (minutes)",
        default=15
    )
    
    return {
        "title": title,
        "style": style,
        "speaker_roles": speaker_roles,
        "target_duration": duration
    }