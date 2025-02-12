from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Confirm
import platform
import subprocess
import os
import logging
import datetime
from typing import Optional
from ..storage.conversation import ConversationStatus, Conversation, ConversationStore
from ..storage.document_store import DocumentStore
from ..services.podcast_generator import PodcastGenerator

logger = logging.getLogger(__name__)

async def handle_add_conversation(
    console: Console,
    conv_store: ConversationStore,
    doc_store: DocumentStore,
    podcast_gen: PodcastGenerator,
    output_dir: Path,
) -> None:
    """Handle the /add conversation command."""
    try:
        # Get all documents
        documents = doc_store.list_documents()
        if not documents:
            console.print("[red]No documents available. Add some documents first.")
            return
        
        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = output_dir / f"podcast_{timestamp}.wav"
        
        # Create pending conversation
        conversation = conv_store.create_pending(
            title=f"Podcast {timestamp}",
            metadata={
                "document_ids": [doc.id for doc in documents],
                "timestamp": timestamp
            }
        )
        
        console.print(f"[yellow]Started generating podcast {conversation.id}...")
        
        try:
            # Generate podcast
            progress_callback = lambda p: conv_store.update_progress(conversation.id, p)
            
            transcript, audio_file = await podcast_gen.generate_podcast(
                doc_ids=[doc.id for doc in documents],
                output_path=audio_path,
                progress_callback=progress_callback
            )
            
            # Update with final content
            conv_store.update_progress(
                conversation.id,
                1.0,
                transcript=transcript,
                audio_path=audio_file
            )
            
            console.print(f"[green]Generated podcast {conversation.id} saved as: {audio_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate podcast: {e}")
            conv_store.mark_failed(conversation.id, str(e))
            console.print(f"[red]Error generating podcast: {str(e)}")
            
    except Exception as e:
        logger.error(f"Failed to start podcast generation: {e}")
        console.print(f"[red]Error: {str(e)}")

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

def handle_remove_conversation(
    console: Console,
    conv_store: ConversationStore,
    conv_id: int
) -> None:
    """Handle the /remove conversation command."""
    conversation = conv_store.get(conv_id)
    if not conversation:
        console.print(f"[red]Conversation not found: {conv_id}")
        return
    
    if Confirm.ask(f"Remove conversation {conv_id}?"):
        if conversation.audio_path and conversation.audio_path.exists():
            try:
                conversation.audio_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove audio file: {e}")
        
        if conv_store.remove(conv_id):
            console.print(f"[green]Removed conversation {conv_id}")
        else:
            console.print("[red]Failed to remove conversation")

def play_conversation(
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
        if platform.system() == "Darwin":  # macOS
            subprocess.run(["afplay", str(conversation.audio_path)])
        elif platform.system() == "Windows":
            os.startfile(conversation.audio_path)
        else:  # Linux and others
            subprocess.run(["xdg-open", str(conversation.audio_path)])
            
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

