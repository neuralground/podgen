"""CLI commands for conversation management."""

from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt, Confirm
import platform
import subprocess
import os
import logging
import datetime
from typing import List, Dict, Any, Optional
import asyncio
from pathlib import Path

from ..storage.conversation import ConversationStatus, Conversation, ConversationStore
from ..storage.document_store import Document, DocumentStore
from ..services.podcast_generator import PodcastGenerator
from ..models.speaker_profiles import (
    DEFAULT_SPEAKER_PROFILES,
    get_default_speakers,
    get_available_styles,
    get_available_speaker_roles
)

logger = logging.getLogger(__name__)

# Import config prompting
from .conversation_config import prompt_conversation_config

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
        "Choose conversation style",
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
        "Target podcast duration (minutes)",
        default=15
    )
    
    return {
        "title": title,
        "style": style,
        "speaker_roles": speaker_roles,
        "target_duration": duration
    }

async def handle_add_conversation(
    console: Console,
    conv_store: ConversationStore,
    doc_store: DocumentStore,
    podcast_gen: PodcastGenerator,
    output_dir: Path,
    debug: bool = False
) -> Optional[asyncio.Task]:
    """Handle the /add conversation command."""
    try:
        # Get all documents
        documents = doc_store.list_documents()
        if not documents:
            console.print("[red]No documents available. Add some documents first.")
            return None
        
        # Get configuration from user
        config = await prompt_conversation_config(console, doc_store, documents)
        
        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = output_dir / f"podcast_{timestamp}.wav"
        
        # Create pending conversation
        conversation = conv_store.create_pending(
            title=config["title"],
            metadata={
                "document_ids": [doc.id for doc in documents],
                "timestamp": timestamp,
                "style": config["style"],
                "speaker_roles": config["speaker_roles"],
                "target_duration": config["target_duration"]
            }
        )

        async def generate_podcast():
            try:
                def progress_callback(progress: float, stage: str = None):
                    conv_store.update_progress(conversation.id, progress)
                    if debug and stage:
                        console.print(f"[yellow]Stage: {stage} - Progress: {progress:.1%}")
                
                if debug:
                    console.print("[yellow]Starting content analysis...")
                transcript, audio_file = await podcast_gen.generate_podcast(
                    doc_ids=[doc.id for doc in documents],
                    output_path=audio_path,
                    progress_callback=progress_callback,
                    config=config,
                    debug=debug
                )
                
                # Update with final content
                conv_store.update_progress(
                    conversation.id,
                    1.0,
                    transcript=transcript,
                    audio_path=audio_file
                )
                
                if debug:
                    console.print("[green]Generation complete!")
                
            except Exception as e:
                logger.error(f"Failed to generate podcast: {e}")
                conv_store.mark_failed(conversation.id, str(e))
                if debug:
                    console.print(f"[red]Generation failed: {str(e)}")
                    import traceback
                    console.print(traceback.format_exc())
        
        if not debug:
            # Start generation in background and return the task
            console.print(f"[green]Started generating podcast {conversation.id} in background.")
            console.print(f"Title: {config['title']}")
            console.print(f"Style: {config['style']}")
            console.print("Use /list conversations to check the status.")
            task = asyncio.create_task(generate_podcast())
            task.conversation_id = conversation.id  # Attach ID for cleanup
            return task
        else:
            # Generate synchronously with debug output
            console.print(f"[yellow]Starting podcast generation in debug mode...")
            console.print(f"Title: {config['title']}")
            console.print(f"Style: {config['style']}")
            await generate_podcast()
            return None
            
    except Exception as e:
        logger.error(f"Failed to start podcast generation: {e}")
        console.print(f"[red]Error: {str(e)}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        return None

def handle_list_conversations(
    console: Console,
    conv_store: ConversationStore
) -> None:
    """Handle the /list conversations command."""
    conversations = conv_store.list_all()
    
    if not conversations:
        console.print("No conversations available")
        return
    
    table = Table("ID", "Title", "Status", "Progress", "Created", "Audio File")
    for conv in conversations:
        # Format status and progress
        if conv.status == ConversationStatus.GENERATING:
            status = f"[yellow]{conv.status.value}"
            progress = f"[yellow]{conv.progress:.0%}"
        elif conv.status == ConversationStatus.COMPLETED:
            status = f"[green]{conv.status.value}"
            progress = "[green]100%"
        else:
            status = f"[red]{conv.status.value}"
            progress = f"[red]{conv.progress:.0%}"
        
        table.add_row(
            str(conv.id),
            conv.title,
            status,
            progress,
            conv.created_date.strftime("%Y-%m-%d %H:%M"),
            str(conv.audio_path) if conv.audio_path else ""
        )
    
    console.print(table)

async def handle_remove_conversation(
    console: Console,
    conv_store: ConversationStore,
    conv_id: int,
    conversation_tasks: Optional[Dict[int, asyncio.Task]] = None
) -> None:
    """Handle the /remove conversation command."""
    conversation = conv_store.get(conv_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conv_id}")
        return
    
    if conversation.status == ConversationStatus.GENERATING:
        if not Confirm.ask(f"[yellow]Conversation {conv_id} is still being generated. Stop generation and remove?"):
            return
            
        # Cancel running task if we have it
        if conversation_tasks and conv_id in conversation_tasks:
            task = conversation_tasks[conv_id]
            if not task.done():
                console.print("[yellow]Cancelling generation task...")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error cancelling task: {e}")
                # Task cleanup handled by callbacks in AsyncApp
    
    # Clean up any output files
    if conversation.audio_path and conversation.audio_path.exists():
        try:
            conversation.audio_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove audio file: {e}")
    
    # Remove from database
    if conv_store.remove(conv_id):
        console.print(f"[green]Removed conversation {conv_id}")
    else:
        console.print("[red]Failed to remove conversation")

async def handle_remove_all_conversations(
    console: Console,
    conv_store: ConversationStore,
    conversation_tasks: Optional[Dict[int, asyncio.Task]] = None
) -> None:
    """Handle the /remove conversations all command."""
    conversations = conv_store.list_all()
    if not conversations:
        console.print("No conversations to remove")
        return
    
    # Count conversations by status
    generating = sum(1 for c in conversations if c.status == ConversationStatus.GENERATING)
    if generating > 0:
        if not Confirm.ask(f"[yellow]{generating} conversations are still generating. Stop all and remove?"):
            return
        
        # Cancel all running tasks
        if conversation_tasks:
            console.print("[yellow]Cancelling generation tasks...")
            for conv in conversations:
                if conv.id in conversation_tasks:
                    task = conversation_tasks[conv.id]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Error cancelling task {conv.id}: {e}")
    
    if Confirm.ask(f"Remove all {len(conversations)} conversations?"):
        # Remove audio files first
        for conv in conversations:
            if conv.audio_path and conv.audio_path.exists():
                try:
                    conv.audio_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove audio file {conv.audio_path}: {e}")
        
        # Remove from database
        success = all(conv_store.remove(conv.id) for conv in conversations)
        if success:
            console.print(f"[green]Removed {len(conversations)} conversations")
        else:
            console.print("[red]Failed to remove some conversations")

def handle_remove_all_sources(
    console: Console,
    doc_store: DocumentStore
) -> None:
    """Handle the /remove sources all command."""
    documents = doc_store.list_documents()
    if not documents:
        console.print("No sources to remove")
        return
        
    if Confirm.ask(f"Remove all {len(documents)} sources?"):
        success = all(doc_store.remove(doc.id) for doc in documents)
        if success:
            console.print(f"[green]Removed {len(documents)} sources")
        else:
            console.print("[red]Failed to remove some sources")

async def play_conversation(
    console: Console,
    conv_store: ConversationStore,
    conv_id: int
) -> None:
    """Play a conversation's audio."""
    conversation = conv_store.get(conv_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conv_id}")
        return
    
    if conversation.status == ConversationStatus.GENERATING:
        console.print("[yellow]This conversation is still being generated. Please wait until it's complete.")
        return
    
    if conversation.status == ConversationStatus.FAILED:
        console.print(f"[red]This conversation failed to generate: {conversation.error}")
        return
    
    if not conversation.audio_path or not conversation.audio_path.exists():
        console.print("[red]Audio file not found")
        return
    
    try:
        # Use appropriate audio player based on platform
        loop = asyncio.get_running_loop()
        if platform.system() == "Darwin":  # macOS
            await loop.run_in_executor(None, lambda: subprocess.run(["afplay", str(conversation.audio_path)]))
        elif platform.system() == "Windows":
            os.startfile(conversation.audio_path)
        else:  # Linux and others
            await loop.run_in_executor(None, lambda: subprocess.run(["xdg-open", str(conversation.audio_path)]))
            
    except Exception as e:
        console.print(f"[red]Failed to play audio: {e}")

def show_conversation(
    console: Console,
    conv_store: ConversationStore,
    conv_id: int
) -> None:
    """Show a conversation's transcript."""
    conversation = conv_store.get(conv_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conv_id}")
        return
    
    if conversation.status == ConversationStatus.GENERATING:
        console.print("[yellow]This conversation is still being generated. Please wait until it's complete.")
        return
    
    if conversation.status == ConversationStatus.FAILED:
        console.print(f"[red]This conversation failed to generate: {conversation.error}")
        return
    
    if not conversation.transcript:
        console.print("[red]No transcript available")
        return
    
    # Display transcript with rich formatting
    console.print("\n[bold]Transcript:[/bold]\n")
    console.print(Markdown(conversation.transcript))

