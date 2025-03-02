"""Podcast generation and management commands for podgen CLI."""

import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.prompt import Prompt, IntPrompt, Confirm
import datetime
import traceback

from ...storage.conversation import ConversationStore, ConversationStatus
from ...storage.document_store import DocumentStore
from ...services.podcast_generator import PodcastGenerator
from ...models.speaker_profiles import (
    DEFAULT_SPEAKER_PROFILES,
    get_default_speakers,
    get_available_styles,
    get_available_speaker_roles
)
from ...config import settings
from ..services.player import AudioPlayer

logger = logging.getLogger(__name__)

class PodcastCommands:
    """Commands for generating and managing podcasts."""
    
    def __init__(
        self, 
        conv_store: Optional[ConversationStore] = None,
        doc_store: Optional[DocumentStore] = None,
        podcast_gen: Optional[PodcastGenerator] = None,
        output_dir: Optional[Path] = None
    ):
        """Initialize with stores and generator."""
        # Use provided services or create from defaults
        self.conv_store = conv_store or ConversationStore(settings.paths.get_db_path("conversations"))
        self.doc_store = doc_store or DocumentStore(settings.paths.get_db_path("documents"))
        self.podcast_gen = podcast_gen
        self.output_dir = output_dir or settings.paths.get_path("output")
        
        # Track background tasks
        self.conversation_tasks: Dict[int, asyncio.Task] = {}
    
    async def create(self, console: Console, args: List[str]) -> None:
        """Create a new podcast from documents."""
        try:
            # Check for debug mode flag
            debug_mode = "--debug" in args
            
            # Get all documents
            documents = self.doc_store.list_documents()
            if not documents:
                console.print("[red]No documents available. Add some documents first.")
                console.print("Use '/doc add <file or URL>' to add a document")
                return

            console.print(f"Found {len(documents)} documents for podcast creation:")
            for doc in documents:
                title = doc.metadata.get('title', '')
                if not title and doc.doc_type == 'file':
                    title = Path(doc.source).name
                elif not title:
                    title = doc.source[:30] + "..." if len(doc.source) > 30 else doc.source
                console.print(f"  - {title}")

            # Get configuration from user
            config_dict = await self._prompt_for_config(console)
            
            console.print("\nConfiguration summary:")
            console.print(f"  Title: {config_dict['title']}")
            console.print(f"  Style: {config_dict['style']}")
            console.print(f"  Speakers: {', '.join(config_dict['speaker_roles'])}")
            console.print(f"  Target duration: {config_dict['target_duration']} minutes")

            # Ensure output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename using path manager
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            audio_path = settings.paths.get_unique_output_path(
                prefix=f"podcast_{timestamp}", 
                suffix=f".{settings.output_format}"
            )

            console.print(f"Output will be saved to: {audio_path}")

            # Create pending conversation
            conversation = self.conv_store.create_pending(
                title=config_dict["title"],
                metadata={
                    "document_ids": [doc.id for doc in documents],
                    "timestamp": timestamp,
                    "style": config_dict["style"],
                    "speaker_roles": config_dict["speaker_roles"],
                    "target_duration": config_dict["target_duration"]
                }
            )

            console.print(f"Created conversation with ID: {conversation.id}")

            if not debug_mode:
                # Start generation in background
                task = asyncio.create_task(self._generate_podcast_async(
                    conversation.id, 
                    [doc.id for doc in documents],
                    audio_path,
                    config_dict
                ))
                task.conversation_id = conversation.id
                self.conversation_tasks[conversation.id] = task
                
                console.print("[green]Podcast generation started in background")
                console.print("Use '/podcast list' to check the status")
            else:
                # Run in foreground with debug output
                console.print("[yellow]Starting podcast generation in debug mode...")
                await self._generate_podcast_debug(
                    conversation.id,
                    [doc.id for doc in documents],
                    audio_path,
                    config_dict,
                    console
                )
                
        except Exception as e:
            logger.error(f"Error creating podcast: {e}")
            console.print(f"[red]Error creating podcast: {str(e)}")
    
    async def list(self, console: Console, args: List[str]) -> None:
        """List all podcasts."""
        try:
            conversations = self.conv_store.list_all()
            
            if not conversations:
                console.print("No podcasts available")
                return
            
            # Create table for display
            table = Table(title=f"Podcasts ({len(conversations)})")
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Title", style="blue")
            table.add_column("Status", style="green")
            table.add_column("Progress", style="yellow")
            table.add_column("Created", style="magenta")
            table.add_column("Duration", style="green", justify="right")
            
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
                
                # Get duration if available
                duration = "-"
                if conv.audio_path and conv.audio_path.exists():
                    try:
                        from ...services.audio import get_audio_duration
                        audio_duration = get_audio_duration(conv.audio_path)
                        if audio_duration:
                            minutes = int(audio_duration) // 60
                            seconds = int(audio_duration) % 60
                            duration = f"{minutes}:{seconds:02d}"
                    except:
                        pass
                
                table.add_row(
                    str(conv.id),
                    conv.title,
                    status,
                    progress,
                    conv.created_date.strftime("%Y-%m-%d %H:%M"),
                    duration
                )
            
            console.print(table)
            
        except Exception as e:
            logger.error(f"Error listing podcasts: {e}")
            console.print(f"[red]Error listing podcasts: {str(e)}")
    
    async def play(self, console: Console, args: List[str]) -> None:
        """Play a podcast."""
        try:
            if not args:
                console.print("[red]Please specify a podcast ID")
                console.print("Usage: /podcast play <id>")
                return
                
            try:
                podcast_id = int(args[0])
            except ValueError:
                console.print("[red]Podcast ID must be a number")
                return
                
            # Get the conversation
            conversation = self.conv_store.get(podcast_id)
            if not conversation:
                console.print(f"[red]Podcast not found: {podcast_id}")
                return
                
            # Check status
            if conversation.status == ConversationStatus.GENERATING:
                console.print("[yellow]This podcast is still being generated")
                console.print(f"Current progress: {conversation.progress:.0%}")
                return
                
            if conversation.status == ConversationStatus.FAILED:
                console.print(f"[red]This podcast failed to generate: {conversation.error}")
                return
                
            # Check for audio file
            if not conversation.audio_path or not conversation.audio_path.exists():
                console.print("[red]Audio file not found")
                return
                
            # Play the audio
            player = AudioPlayer(console)
            await player.play(conversation.audio_path, title=conversation.title)
            
        except Exception as e:
            logger.error(f"Error playing podcast: {e}")
            console.print(f"[red]Error playing podcast: {str(e)}")
    
    async def show(self, console: Console, args: List[str]) -> None:
        """Show podcast details."""
        try:
            if not args:
                console.print("[red]Please specify a podcast ID")
                console.print("Usage: /podcast show <id>")
                return
                
            try:
                podcast_id = int(args[0])
            except ValueError:
                console.print("[red]Podcast ID must be a number")
                return
                
            # Get the conversation
            conversation = self.conv_store.get(podcast_id)
            if not conversation:
                console.print(f"[red]Podcast not found: {podcast_id}")
                return
                
            # Display podcast details
            console.print(f"\n[bold]Podcast {podcast_id}: {conversation.title}[/bold]")
            console.print(f"Status: {conversation.status.value}")
            console.print(f"Created: {conversation.created_date.strftime('%Y-%m-%d %H:%M')}")
            
            # Display progress if generating
            if conversation.status == ConversationStatus.GENERATING:
                console.print(f"Progress: {conversation.progress:.0%}")
            
            # Display error if failed
            if conversation.status == ConversationStatus.FAILED:
                console.print(f"Error: {conversation.error}")
            
            # Display metadata
            console.print("\n[bold]Configuration:[/bold]")
            if conversation.metadata:
                # Style and speakers
                style = conversation.metadata.get("style", "Not specified")
                console.print(f"Style: {style}")
                
                speaker_roles = conversation.metadata.get("speaker_roles", [])
                if speaker_roles:
                    console.print("\n[bold]Speakers:[/bold]")
                    for role in speaker_roles:
                        speaker = DEFAULT_SPEAKER_PROFILES.get(role)
                        if speaker:
                            console.print(f"- {speaker.name} ({role})")
                
                # Target duration
                target_duration = conversation.metadata.get("target_duration", "Not specified")
                console.print(f"\nTarget duration: {target_duration} minutes")
                
                # Source documents
                doc_ids = conversation.metadata.get("document_ids", [])
                if doc_ids:
                    console.print("\n[bold]Source Documents:[/bold]")
                    for doc_id in doc_ids:
                        doc = self.doc_store.get_document(doc_id)
                        if doc:
                            title = doc.metadata.get('title', '')
                            if not title and doc.doc_type == 'file':
                                title = Path(doc.source).name
                            elif not title:
                                title = doc.source[:30] + "..." if len(doc.source) > 30 else doc.source
                            console.print(f"- {title} (ID: {doc_id})")
            
            # Display audio information
            if conversation.audio_path:
                console.print("\n[bold]Audio:[/bold]")
                console.print(f"Path: {conversation.audio_path}")
                
                if conversation.audio_path.exists():
                    # Get file size
                    size_bytes = conversation.audio_path.stat().st_size
                    if size_bytes > 1024*1024:
                        size = f"{size_bytes/1024/1024:.1f} MB"
                    elif size_bytes > 1024:
                        size = f"{size_bytes/1024:.1f} KB"
                    else:
                        size = f"{size_bytes} bytes"
                    console.print(f"Size: {size}")
                    
                    # Get duration
                    try:
                        from ...services.audio import get_audio_duration
                        duration = get_audio_duration(conversation.audio_path)
                        if duration:
                            minutes = int(duration) // 60
                            seconds = int(duration) % 60
                            console.print(f"Duration: {minutes}:{seconds:02d}")
                    except:
                        pass
                else:
                    console.print("[red]Audio file not found on disk")
            
            # Display transcript
            if conversation.transcript:
                console.print("\n[bold]Transcript:[/bold]")
                console.print(Markdown(conversation.transcript[:500] + "..." if len(conversation.transcript) > 500 else conversation.transcript))
                
                if len(conversation.transcript) > 500:
                    if Confirm.ask("Show full transcript?"):
                        console.print(Markdown(conversation.transcript))
            
        except Exception as e:
            logger.error(f"Error showing podcast: {e}")
            console.print(f"[red]Error showing podcast: {str(e)}")
    
    async def remove(self, console: Console, args: List[str]) -> None:
        """Remove a podcast."""
        try:
            if not args:
                console.print("[red]Please specify a podcast ID")
                console.print("Usage: /podcast remove <id>")
                return
                
            try:
                podcast_id = int(args[0])
            except ValueError:
                console.print("[red]Podcast ID must be a number")
                return
                
            # Get the conversation
            conversation = self.conv_store.get(podcast_id)
            if not conversation:
                console.print(f"[red]Podcast not found: {podcast_id}")
                return
                
            # Check if generating
            if conversation.status == ConversationStatus.GENERATING:
                # Check if force flag
                force = "--force" in args
                if not force:
                    if not Confirm.ask(f"Podcast {podcast_id} is still generating. Stop and remove?"):
                        console.print("[yellow]Operation cancelled")
                        return
                
                # Cancel generating task
                if podcast_id in self.conversation_tasks:
                    task = self.conversation_tasks[podcast_id]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Error cancelling task: {e}")
            
            # Confirm removal
            force = "--force" in args
            if not force and conversation.status == ConversationStatus.COMPLETED:
                if not Confirm.ask(f"Remove podcast {podcast_id}: {conversation.title}?"):
                    console.print("[yellow]Operation cancelled")
                    return
            
            # Remove audio file
            if conversation.audio_path and conversation.audio_path.exists():
                try:
                    conversation.audio_path.unlink()
                except Exception as e:
                    logger.error(f"Error removing audio file: {e}")
                    console.print(f"[yellow]Could not remove audio file: {e}")
            
            # Remove from database
            if self.conv_store.remove(podcast_id):
                console.print(f"[green]Removed podcast {podcast_id}")
            else:
                console.print(f"[red]Failed to remove podcast {podcast_id}")
                
        except Exception as e:
            logger.error(f"Error removing podcast: {e}")
            console.print(f"[red]Error removing podcast: {str(e)}")
    
    async def remove_all(self, console: Console, args: List[str]) -> None:
        """Remove all podcasts."""
        try:
            conversations = self.conv_store.list_all()
            
            if not conversations:
                console.print("No podcasts to remove")
                return
                
            # Count generating conversations
            generating = sum(1 for c in conversations if c.status == ConversationStatus.GENERATING)
            
            # Check if force flag
            force = "--force" in args
            if not force:
                if generating > 0:
                    warning = f"{generating} podcast(s) still generating."
                console.print(f"[yellow]About to remove {len(conversations)} podcasts")
                if generating > 0:
                    console.print(f"[yellow]{warning} These will be stopped.")
                
                if not Confirm.ask("Continue with removal?"):
                    console.print("[yellow]Operation cancelled")
                    return
            
            # Cancel generating tasks
            for conv in conversations:
                if conv.status == ConversationStatus.GENERATING:
                    if conv.id in self.conversation_tasks:
                        task = self.conversation_tasks[conv.id]
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                            except Exception as e:
                                logger.error(f"Error cancelling task: {e}")
            
            # Remove audio files
            failed_files = 0
            for conv in conversations:
                if conv.audio_path and conv.audio_path.exists():
                    try:
                        conv.audio_path.unlink()
                    except Exception as e:
                        logger.error(f"Error removing audio file: {e}")
                        failed_files += 1
            
            # Remove from database
            success = all(self.conv_store.remove(conv.id) for conv in conversations)
            
            if success:
                console.print(f"[green]Removed {len(conversations)} podcasts")
                if failed_files > 0:
                    console.print(f"[yellow]Could not remove {failed_files} audio files")
            else:
                console.print("[red]Failed to remove some podcasts")
                
        except Exception as e:
            logger.error(f"Error removing all podcasts: {e}")
            console.print(f"[red]Error removing all podcasts: {str(e)}")
    
    async def _prompt_for_config(self, console: Console) -> Dict[str, Any]:
        """Prompt user for podcast configuration."""
        # Get podcast title
        default_title = f"Podcast {datetime.datetime.now().strftime('%Y-%m-%d')}"
        title = Prompt.ask("Enter podcast title", default=default_title)
        
        # Show available styles
        console.print("\nAvailable conversation styles:")
        styles = get_available_styles()
        for style in styles:
            speakers = get_default_speakers(style)
            speaker_names = [s.name for s in speakers]
            console.print(f"  {style}: {', '.join(speaker_names)}")
        
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
        role_table = Table()
        role_table.add_column("Role", style="cyan")
        role_table.add_column("Name", style="green")
        role_table.add_column("Style", style="blue")
        
        roles = get_available_speaker_roles()
        for role in roles:
            speaker = DEFAULT_SPEAKER_PROFILES.get(role)
            if speaker:
                role_table.add_row(role, speaker.name, speaker.style[:50] + "..." if len(speaker.style) > 50 else speaker.style)
        
        console.print(role_table)
        
        for i, default_speaker in enumerate(default_speakers):
            role_name = ["Host", "Co-host", "Guest"][i] if i < 3 else f"Speaker {i+1}"
            
            # Get default role for this speaker
            default_role = next(
                (role for role, speaker in DEFAULT_SPEAKER_PROFILES.items() 
                 if speaker.name == default_speaker.name),
                roles[0]
            )
            
            role = Prompt.ask(
                f"Choose {role_name} role",
                choices=roles,
                default=default_role
            )
            speaker_roles.append(role)
        
        # Get target duration
        target_duration = IntPrompt.ask(
            "Target podcast duration (minutes)",
            default=15
        )
        
        return {
            "title": title,
            "style": style,
            "speaker_roles": speaker_roles,
            "target_duration": target_duration
        }
    
    async def _generate_podcast_async(
        self,
        conversation_id: int,
        doc_ids: List[int],
        output_path: Path,
        config: Dict[str, Any]
    ) -> None:
        """Generate podcast asynchronously."""
        try:
            if not self.podcast_gen:
                raise ValueError("Podcast generator not initialized")
                
            def progress_callback(progress: float, stage: str = None):
                self.conv_store.update_progress(conversation_id, progress)
            
            # Generate podcast
            transcript, audio_file = await self.podcast_gen.generate_podcast(
                doc_ids=doc_ids,
                output_path=output_path,
                progress_callback=progress_callback,
                config=config,
                debug=False
            )
            
            # Update conversation with results
            self.conv_store.update_progress(
                conversation_id,
                1.0,
                transcript=transcript,
                audio_path=audio_file
            )
            
            logger.info(f"Podcast {conversation_id} generated successfully")
            
        except asyncio.CancelledError:
            logger.info(f"Podcast generation {conversation_id} cancelled")
            self.conv_store.mark_failed(conversation_id, "Cancelled by user")
            raise
            
        except Exception as e:
            logger.error(f"Failed to generate podcast {conversation_id}: {e}")
            self.conv_store.mark_failed(conversation_id, str(e))
            
    async def _generate_podcast_debug(
        self,
        conversation_id: int,
        doc_ids: List[int],
        output_path: Path,
        config: Dict[str, Any],
        console: Console
    ) -> None:
        """Generate podcast in debug mode with console output."""
        try:
            if not self.podcast_gen:
                raise ValueError("Podcast generator not initialized")
                
            def progress_callback(progress: float, stage: str = None):
                self.conv_store.update_progress(conversation_id, progress)
                if stage:
                    console.print(f"[yellow]{stage} - Progress: {progress:.1%}")
            
            # Generate podcast with debug output
            console.print("\n[yellow]Starting podcast generation...")
            console.print("[yellow]Step 1: Content Analysis")
            
            transcript, audio_file = await self.podcast_gen.generate_podcast(
                doc_ids=doc_ids,
                output_path=output_path,
                progress_callback=progress_callback,
                config=config,
                debug=True
            )
            
            # Update conversation with results
            self.conv_store.update_progress(
                conversation_id,
                1.0,
                transcript=transcript,
                audio_path=audio_file
            )
            
            console.print("\n[green]Generation complete!")
            console.print(f"Generated transcript ({len(transcript)} chars)")
            console.print(f"Audio saved to: {audio_file}")
            
        except Exception as e:
            logger.error(f"Failed to generate podcast: {e}")
            console.print("\n[red]Generation failed!")
            console.print(f"Error: {str(e)}")
            self.conv_store.mark_failed(conversation_id, str(e))
            console.print_exception()

def register_commands(registry):
    """Register podcast commands with the registry."""
    podcast_commands = PodcastCommands()
    
    # Register main command
    registry.register(
        "podcast", 
        podcast_commands.list,
        "Create and manage podcasts"
    )
    
    # Register subcommands
    registry.register_subcommand(
        "podcast", "create", 
        podcast_commands.create,
        "Create a new podcast from documents"
    )
    
    registry.register_subcommand(
        "podcast", "list", 
        podcast_commands.list,
        "List all podcasts"
    )
    
    registry.register_subcommand(
        "podcast", "play", 
        podcast_commands.play,
        "Play a podcast"
    )
    
    registry.register_subcommand(
        "podcast", "show", 
        podcast_commands.show,
        "Show podcast details"
    )
    
    registry.register_subcommand(
        "podcast", "remove", 
        podcast_commands.remove,
        "Remove a podcast"
    )
    
    registry.register_subcommand(
        "podcast", "remove-all", 
        podcast_commands.remove_all,
        "Remove all podcasts"
    )
    
    # Aliases for backward compatibility
    registry.register(
        "add", 
        lambda console, args: podcast_commands.create(console, []) if args and args[0] == "conversation" else None,
        "Create podcast (alias for /podcast create)"
    )
    
    registry.register(
        "list", 
        lambda console, args: podcast_commands.list(console, []) if args and args[0] == "conversations" else None,
        "List podcasts (alias for /podcast list)"
    )
    
    registry.register(
        "play", 
        lambda console, args: podcast_commands.play(console, args),
        "Play podcast (alias for /podcast play)"
    )
    