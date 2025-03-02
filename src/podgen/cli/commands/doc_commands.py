"""Document management commands for podgen CLI."""

import logging
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
import urllib.parse
import time
import os

from ...storage.document_store import DocumentStore
from ...config import settings

logger = logging.getLogger(__name__)

class DocumentCommands:
    """Commands for managing documents."""
    
    def __init__(self, doc_store: DocumentStore = None):
        """Initialize with document store."""
        self.doc_store = doc_store or DocumentStore(settings.paths.get_db_path("documents"))
    
    async def add(self, console: Console, args: List[str]) -> None:
        """Add a document to the collection."""
        try:
            if not args:
                console.print("[red]Please provide a file path or URL")
                console.print("Usage: /doc add <file path or URL>")
                return
                
            source = " ".join(args)  # Join all args as the source
            
            # Try to parse as URL first
            try:
                parsed_url = urllib.parse.urlparse(source)
                if parsed_url.scheme and parsed_url.netloc:  # Valid URL
                    await self._add_url(console, source)
                    return
            except Exception:
                pass  # Not a URL, continue with file handling
            
            # Handle as file path
            try:
                path = Path(source).resolve()
                if not path.exists():
                    console.print(f"[red]File not found: {path}")
                    return
                    
                await self._add_file(console, path)
            except Exception as e:
                console.print(f"[red]Error adding file: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            console.print(f"[red]Error adding document: {str(e)}")
    
    async def list(self, console: Console, args: List[str]) -> None:
        """List documents in the collection."""
        try:
            documents = self.doc_store.list_documents()
            
            if not documents:
                console.print("No documents in collection")
                return
                
            # Create a formatted table
            table = Table(title=f"Documents ({len(documents)})")
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Type", style="green")
            table.add_column("Title", style="blue")
            table.add_column("Source", style="yellow")
            table.add_column("Added", style="magenta")
            table.add_column("Size", style="green", justify="right")
            
            for doc in documents:
                # Format the added date
                added_date = doc.added_date.strftime("%Y-%m-%d %H:%M")
                
                # Determine size
                size = "N/A"
                if doc.local_path:
                    try:
                        file_size = Path(doc.local_path).stat().st_size
                        if file_size > 1_000_000:
                            size = f"{file_size/1_000_000:.1f} MB"
                        elif file_size > 1_000:
                            size = f"{file_size/1_000:.1f} KB"
                        else:
                            size = f"{file_size} B"
                    except:
                        pass
                elif doc.extracted_text:
                    text_size = len(doc.extracted_text)
                    if text_size > 1_000_000:
                        size = f"{text_size/1_000_000:.1f} MB"
                    elif text_size > 1_000:
                        size = f"{text_size/1_000:.1f} KB"
                    else:
                        size = f"{text_size} B"
                
                # Get title
                title = doc.metadata.get('title', '')
                if not title and doc.doc_type == 'file':
                    title = Path(doc.source).name
                elif not title:
                    title = doc.source[:30] + "..." if len(doc.source) > 30 else doc.source
                
                # Add the row
                table.add_row(
                    str(doc.id),
                    doc.doc_type,
                    title,
                    doc.source[:40] + "..." if len(doc.source) > 40 else doc.source,
                    added_date,
                    size
                )
                
            console.print(table)
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            console.print(f"[red]Error listing documents: {str(e)}")
    
    async def remove(self, console: Console, args: List[str]) -> None:
        """Remove a document from the collection."""
        try:
            if not args:
                console.print("[red]Please specify a document ID")
                console.print("Usage: /doc remove <id>")
                return
                
            try:
                doc_id = int(args[0])
            except ValueError:
                console.print("[red]Document ID must be a number")
                return
                
            # Check if document exists
            doc = self.doc_store.get_document(doc_id)
            if not doc:
                console.print(f"[red]Document not found: {doc_id}")
                return
                
            # Confirm removal
            force = "--force" in args
            if not force:
                title = doc.metadata.get('title', '')
                if not title and doc.doc_type == 'file':
                    title = Path(doc.source).name
                elif not title:
                    title = doc.source[:30] + "..." if len(doc.source) > 30 else doc.source
                    
                if not Confirm.ask(f"Remove document {doc_id}: {title}?"):
                    console.print("[yellow]Operation cancelled")
                    return
            
            # Remove the document
            if self.doc_store.remove(doc_id):
                console.print(f"[green]Removed document {doc_id}")
            else:
                console.print(f"[red]Failed to remove document {doc_id}")
                
        except Exception as e:
            logger.error(f"Error removing document: {e}")
            console.print(f"[red]Error removing document: {str(e)}")
    
    async def remove_all(self, console: Console, args: List[str]) -> None:
        """Remove all documents from the collection."""
        try:
            documents = self.doc_store.list_documents()
            
            if not documents:
                console.print("No documents to remove")
                return
                
            # Confirm removal
            force = "--force" in args
            if not force:
                if not Confirm.ask(f"Remove all {len(documents)} documents?"):
                    console.print("[yellow]Operation cancelled")
                    return
                
            # Remove all documents
            success = True
            for doc in documents:
                if not self.doc_store.remove(doc.id):
                    success = False
                    console.print(f"[red]Failed to remove document {doc.id}")
            
            if success:
                console.print(f"[green]Removed {len(documents)} documents")
            
        except Exception as e:
            logger.error(f"Error removing all documents: {e}")
            console.print(f"[red]Error removing all documents: {str(e)}")
    
    async def info(self, console: Console, args: List[str]) -> None:
        """Show detailed information about a document."""
        try:
            if not args:
                console.print("[red]Please specify a document ID")
                console.print("Usage: /doc info <id>")
                return
                
            try:
                doc_id = int(args[0])
            except ValueError:
                console.print("[red]Document ID must be a number")
                return
                
            # Get the document
            doc = self.doc_store.get_document(doc_id)
            if not doc:
                console.print(f"[red]Document not found: {doc_id}")
                return
                
            # Display document information
            console.print(f"[bold]Document {doc_id}[/bold]")
            console.print(f"Type: {doc.doc_type}")
            console.print(f"Source: {doc.source}")
            
            # Format dates
            console.print(f"Added: {doc.added_date.strftime('%Y-%m-%d %H:%M:%S')}")
            console.print(f"Last accessed: {doc.last_accessed.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Show metadata
            console.print("\n[bold]Metadata:[/bold]")
            for key, value in doc.metadata.items():
                if value:  # Skip empty values
                    console.print(f"{key}: {value}")
            
            # Show content stats
            console.print("\n[bold]Content:[/bold]")
            if doc.extracted_text:
                text_size = len(doc.extracted_text)
                word_count = len(doc.extracted_text.split())
                console.print(f"Size: {text_size:,} characters")
                console.print(f"Words: {word_count:,}")
                
                # Show preview
                preview = doc.extracted_text[:500].replace('\n', ' ')
                if len(doc.extracted_text) > 500:
                    preview += "..."
                console.print("\n[bold]Preview:[/bold]")
                console.print(preview)
            else:
                console.print("[yellow]No extracted text available")
                
        except Exception as e:
            logger.error(f"Error showing document info: {e}")
            console.print(f"[red]Error showing document info: {str(e)}")
    
    async def _add_file(self, console: Console, file_path: Path) -> None:
        """Add a file to the document store."""
        with console.status(f"Adding file {file_path}..."):
            try:
                doc = await self.doc_store.add_file(file_path)
                console.print(f"[green]Added file: {file_path}")
                console.print(f"Document ID: {doc.id}")
            except ValueError as e:
                console.print(f"[red]{str(e)}")
            except Exception as e:
                console.print(f"[red]Error adding file: {str(e)}")
    
    async def _add_url(self, console: Console, url: str) -> None:
        """Add a URL to the document store."""
        with console.status(f"Adding URL {url}..."):
            try:
                doc = await self.doc_store.add_url(url)
                console.print(f"[green]Added URL: {url}")
                console.print(f"Document ID: {doc.id}")
                
                # Show metadata if available
                if doc.metadata:
                    if 'title' in doc.metadata:
                        console.print(f"Title: {doc.metadata['title']}")
                    if 'description' in doc.metadata:
                        console.print(f"Description: {doc.metadata['description']}")
            except ValueError as e:
                console.print(f"[red]{str(e)}")
            except Exception as e:
                console.print(f"[red]Error adding URL: {str(e)}")

def register_commands(registry):
    """Register document commands with the registry."""
    doc_commands = DocumentCommands()
    
    # Register main command
    registry.register(
        "doc", 
        doc_commands.list,
        "Manage documents"
    )
    
    # Register subcommands
    registry.register_subcommand(
        "doc", "add", 
        doc_commands.add,
        "Add a document to the collection"
    )
    
    registry.register_subcommand(
        "doc", "list", 
        doc_commands.list,
        "List documents in the collection"
    )
    
    registry.register_subcommand(
        "doc", "remove", 
        doc_commands.remove,
        "Remove a document from the collection"
    )
    
    registry.register_subcommand(
        "doc", "remove-all", 
        doc_commands.remove_all,
        "Remove all documents from the collection"
    )
    
    registry.register_subcommand(
        "doc", "info", 
        doc_commands.info,
        "Show detailed information about a document"
    )
    
    # Aliases for backward compatibility
    registry.register(
        "add", 
        lambda console, args: doc_commands.add(console, ["source"] + args) if args and args[0] == "source" else None,
        "Add content (alias for /doc add)"
    )
    
    registry.register(
        "list", 
        lambda console, args: doc_commands.list(console, []) if args and args[0] == "sources" else None,
        "List content (alias for /doc list)"
    )
    