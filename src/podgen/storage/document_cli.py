"""CLI commands for document management with async support."""

from pathlib import Path
from typing import Optional
from rich.table import Table
from rich.console import Console
from rich.prompt import Confirm
from datetime import datetime
import urllib.parse
from ..storage.document_store import DocumentStore

async def handle_doc_command(cmd: str, doc_store: DocumentStore, console: Console) -> None:
    """Handle document management commands asynchronously"""
    parts = cmd[1:].split()  # Remove leading slash
    if not parts:
        _show_doc_help(console)
        return
        
    command = parts[0]
    args = parts[1:]
    
    try:
        if command == "add":
            if not args:
                console.print("[red]Please specify a file path or URL")
                return
                
            source = " ".join(args)  # Handle paths/URLs with spaces
            
            # Check if it's a URL
            try:
                parsed = urllib.parse.urlparse(source)
                if parsed.scheme and parsed.netloc:  # Valid URL
                    doc = await doc_store.add_url(source)
                    console.print(f"[green]Added URL: {source}")
                    return
            except:
                pass
                
            # Try as file path
            try:
                path = Path(source).resolve()
                doc = await doc_store.add_file(path)
                console.print(f"[green]Added file: {path}")
            except FileNotFoundError:
                console.print(f"[red]File not found: {source}")
            except ValueError as e:
                console.print(f"[red]{str(e)}")
                
        elif command == "list":
            docs = doc_store.list_documents()
            if not docs:
                console.print("No documents in collection")
                return
                
            table = Table("ID", "Type", "Source", "Added Date")
            for doc in docs:
                added = doc.added_date.strftime("%Y-%m-%d %H:%M")
                table.add_row(
                    str(doc.id),
                    doc.doc_type,
                    doc.source,
                    added
                )
            console.print(table)
            
        elif command == "remove":
            if not args:
                console.print("[red]Please specify document ID")
                return
                
            try:
                doc_id = int(args[0])
                doc = doc_store.get_document(doc_id)
                if not doc:
                    console.print(f"[red]Document not found: {doc_id}")
                    return
                    
                if Confirm.ask(f"Remove {doc.source}?"):
                    if doc_store.remove(doc_id):
                        console.print(f"[green]Removed document: {doc.source}")
                    else:
                        console.print("[red]Failed to remove document")
            except ValueError:
                console.print("[red]Invalid document ID")
                
        else:
            _show_doc_help(console)
            
    except Exception as e:
        console.print(f"[red]Error: {str(e)}")

def _show_doc_help(console: Console):
    """Show document management help"""
    console.print("Document management commands:")
    console.print("  /add <file or URL> - Add document to collection")
    console.print("  /list - List all documents")
    console.print("  /remove <id> - Remove document by ID")

