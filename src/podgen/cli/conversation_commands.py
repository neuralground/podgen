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

        if debug:
            console.print("\n[yellow]Starting conversation generation in debug mode...")
            console.print(f"Found {len(documents)} documents to process:")
            for doc in documents:
                console.print(f"  - {doc.title} ({doc.doc_type})")

        # Get configuration from user
        config = await prompt_conversation_config(console, doc_store, documents)

        if debug:
            console.print("\n[yellow]Configuration:")
            console.print(f"  Title: {config['title']}")
            console.print(f"  Style: {config['style']}")
            console.print(f"  Speakers: {', '.join(config['speaker_roles'])}")
            console.print(f"  Target duration: {config['target_duration']} minutes")

        # Create output directory if needed
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = output_dir / f"podcast_{timestamp}.wav"

        if debug:
            console.print(f"\n[yellow]Output will be saved to: {audio_path}")

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

        if debug:
            console.print(f"\n[yellow]Created pending conversation with ID: {conversation.id}")

        if not debug:
            # For non-debug mode, start generation in background
            async def generate_podcast():
                try:
                    def progress_callback(progress: float, stage: str = None):
                        conv_store.update_progress(conversation.id, progress)

                    transcript, audio_file = await podcast_gen.generate_podcast(
                        doc_ids=[doc.id for doc in documents],
                        output_path=audio_path,
                        progress_callback=progress_callback,
                        config=config,
                        debug=False
                    )

                    conv_store.update_progress(
                        conversation.id,
                        1.0,
                        transcript=transcript,
                        audio_path=audio_file
                    )

                except Exception as e:
                    logger.error(f"Failed to generate podcast: {e}")
                    conv_store.mark_failed(conversation.id, str(e))

            console.print(f"[green]Started generating podcast {conversation.id} in background.")
            console.print(f"Title: {config['title']}")
            console.print(f"Style: {config['style']}")
            console.print("Use /list conversations to check the status.")
            task = asyncio.create_task(generate_podcast())
            task.conversation_id = conversation.id
            return task

        else:
            # Debug mode - run directly in foreground
            try:
                def progress_callback(progress: float, stage: str = None):
                    conv_store.update_progress(conversation.id, progress)
                    if stage:
                        console.print(f"[yellow]Stage: {stage}")
                        console.print(f"Progress: {progress:.1%}")

                console.print("\n[yellow]Starting podcast generation...")
                console.print("[yellow]Step 1: Content Analysis")

                # Generate podcast with debug output
                transcript, audio_file = await podcast_gen.generate_podcast(
                    doc_ids=[doc.id for doc in documents],
                    output_path=audio_path,
                    progress_callback=progress_callback,
                    config=config,
                    debug=True  # Enable debug in podcast generator
                )

                # Update final status
                conv_store.update_progress(
                    conversation.id,
                    1.0,
                    transcript=transcript,
                    audio_path=audio_file
                )

                console.print("\n[green]Generation complete!")
                console.print(f"Generated transcript ({len(transcript)} chars)")
                console.print(f"Audio saved to: {audio_file}")

                return None

            except Exception as e:
                logger.error(f"Failed to generate podcast: {e}")
                console.print(f"\n[red]Generation failed!")
                console.print(f"Error: {str(e)}")
                conv_store.mark_failed(conversation.id, str(e))
                import traceback
                console.print(traceback.format_exc())
                return None

    except Exception as e:
        logger.error(f"Failed to start podcast generation: {e}")
        console.print(f"[red]Error: {str(e)}")
        if debug:
            import traceback
            console.print(traceback.format_exc())
        return None

async def handle_add_conversation_debug(
    console: Console,
    conv_store: ConversationStore,
    doc_store: DocumentStore,
    podcast_gen: PodcastGenerator,
    output_dir: Path
) -> None:
    """Handle conversation generation in debug mode with visible step-by-step output."""
    try:
        # Get all documents
        console.print("\n[yellow]Step 1: Loading Documents")
        documents = doc_store.list_documents()
        if not documents:
            console.print("[red]No documents available. Add some documents first.")
            return

        console.print(f"Found {len(documents)} documents:")
        for doc in documents:
            console.print(f"  - {doc.title} ({doc.doc_type})")

        # Get configuration from user
        console.print("\n[yellow]Step 2: Configuration")
        config = await prompt_conversation_config(console, doc_store, documents)
        
        console.print("\nConfiguration:")
        console.print(f"  Title: {config['title']}")
        console.print(f"  Style: {config['style']}")
        console.print(f"  Speakers: {', '.join(config['speaker_roles'])}")
        console.print(f"  Target duration: {config['target_duration']} minutes")
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_path = output_dir / f"podcast_{timestamp}.wav"
        console.print(f"\nOutput will be saved to: {audio_path}")
        
        # Create conversation record
        console.print("\n[yellow]Step 3: Creating Conversation Record")
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
        console.print(f"Created conversation with ID: {conversation.id}")

        # Define progress callback
        def progress_callback(progress: float, stage: str = None):
            conv_store.update_progress(conversation.id, progress)
            if stage:
                console.print(f"[yellow]{stage} - Progress: {progress:.1%}")

        # Generate podcast
        console.print("\n[yellow]Step 4: Generating Podcast")
        try:
            transcript, audio_file = await podcast_gen.generate_podcast(
                doc_ids=[doc.id for doc in documents],
                output_path=audio_path,
                progress_callback=progress_callback,
                config=config,
                debug=True
            )
            
            # Update final status
            conv_store.update_progress(
                conversation.id,
                1.0,
                transcript=transcript,
                audio_path=audio_file
            )
            
            console.print("\n[green]Generation Complete!")
            console.print(f"Generated transcript ({len(transcript)} chars)")
            console.print(f"Audio saved to: {audio_file}")
            
        except Exception as e:
            console.print(f"\n[red]Generation failed!")
            console.print(f"Error: {str(e)}")
            conv_store.mark_failed(conversation.id, str(e))
            import traceback
            console.print(traceback.format_exc())
            
    except Exception as e:
        console.print(f"\n[red]Setup failed!")
        console.print(f"Error: {str(e)}")
        import traceback
        console.print(traceback.format_exc())

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

async def handle_remove_all_sources(
    console: Console,
    doc_store: DocumentStore
) -> None:
    """Handle the /remove all sources command."""
    documents = doc_store.list_documents()
    if not documents:
        console.print("No sources to remove")
        return
        
    if Confirm.ask(f"Remove all {len(documents)} sources?"):
        # Use list comprehension to handle potential async operations
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

# In src/podgen/cli/conversation_commands.py

def show_conversation(
    console: Console,
    conv_store: ConversationStore,
    doc_store: DocumentStore,
    conv_id: int
) -> None:
    """Show a conversation's details and transcript."""
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
    
    # Display podcast metadata
    console.print("\n[bold blue]Podcast Details:[/bold blue]")
    console.print(f"Title: {conversation.title}")
    console.print(f"Created: {conversation.created_date.strftime('%Y-%m-%d %H:%M')}")
    console.print(f"Status: [green]{conversation.status.value}[/green]")
    
    # Get conversation style and speakers
    metadata = conversation.metadata
    style = metadata.get('style', 'Not specified')
    console.print(f"\nConversation Style: {style}")
    
    # Display speakers and their roles
    speaker_roles = metadata.get('speaker_roles', [])
    if speaker_roles:
        console.print("\n[bold]Speakers:[/bold]")
        for role in speaker_roles:
            speaker = DEFAULT_SPEAKER_PROFILES.get(role)
            if speaker:
                console.print(f"- {speaker.name}: {speaker.style}")
    
    # Display source documents
    doc_ids = metadata.get('document_ids', [])
    if doc_ids:
        console.print("\n[bold]Source Documents:[/bold]")
        for doc_id in doc_ids:
            doc = doc_store.get_document(doc_id)
            if doc:
                console.print(f"- {doc.title} ({doc.doc_type})")
                if doc.metadata.get('url'):
                    console.print(f"  URL: {doc.metadata['url']}")
    
    # Display model information
    console.print("\n[bold]Model Information:[/bold]")
    llm_provider = metadata.get('llm_provider', 'Not specified')
    llm_model = metadata.get('llm_model', 'Not specified')
    tts_provider = metadata.get('tts_provider', 'Not specified')
    tts_model = metadata.get('tts_model', 'Not specified')
    
    console.print(f"Content Analysis & Dialogue: {llm_provider} ({llm_model})")
    console.print(f"Text-to-Speech: {tts_provider}" + (f" ({tts_model})" if tts_model != 'Not specified' else ""))
    
    # Display audio information if available
    if conversation.audio_path:
        console.print(f"\nAudio File: {conversation.audio_path}")
        try:
            size = conversation.audio_path.stat().st_size
            if size > 1024*1024:
                size = f"{size/(1024*1024):.1f}MB"
            elif size > 1024:
                size = f"{size/1024:.1f}KB"
            else:
                size = f"{size}B"
            console.print(f"File Size: {size}")
        except:
            pass
    
    # Display transcript
    if conversation.transcript:
        console.print("\n[bold]Transcript:[/bold]\n")
        console.print(Markdown(conversation.transcript))
    else:
        console.print("\n[red]No transcript available[/red]")

