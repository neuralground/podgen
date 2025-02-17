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
    print(f"DEBUG: Handling document command: {cmd}")
    parts = cmd[1:].split()  # Remove leading slash
    if not parts:
        _show_doc_help(console)
        return

    command = parts[0].lower()
    args = parts[1:]
    print(f"DEBUG: Command: {command}, Args: {args}")

    try:
        if command == "add" and len(args) >= 2 and args[0] == "source":
            source = " ".join(args[1:])  # Everything after "source"
            print(f"DEBUG: Adding source: {source}")

            # Check if it's a URL
            try:
                parsed = urllib.parse.urlparse(source)
                if parsed.scheme and parsed.netloc:  # Valid URL
                    doc = await doc_store.add_url(source)
                    console.print(f"[green]Added URL: {source}")
                    return
            except Exception as e:
                print(f"DEBUG: Not a URL: {e}")

            # Try as file path
            try:
                path = Path(source).resolve()
                print(f"DEBUG: Resolved path: {path}")
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {path}")

                doc = await doc_store.add_file(path)
                console.print(f"[green]Added file: {path}")
            except FileNotFoundError as e:
                console.print(f"[red]{str(e)}")
            except ValueError as e:
                console.print(f"[red]{str(e)}")
            except Exception as e:
                print(f"DEBUG: Error adding file: {type(e).__name__}: {e}")
                console.print(f"[red]Error adding file: {str(e)}")

        elif command == "list" and args and args[0] == "sources":
            print("DEBUG: Listing sources")
            docs = doc_store.list_documents()
            print(f"DEBUG: Found {len(docs)} documents")

            if not docs:
                console.print("No documents in collection")
                return

            table = Table("ID", "Type", "Source", "Added Date", "Size")
            for doc in docs:
                try:
                    added = doc.added_date.strftime("%Y-%m-%d %H:%M")
                    size = "N/A"
                    if doc.local_path:
                        try:
                            size = Path(doc.local_path).stat().st_size
                            if size > 1024*1024:
                                size = f"{size/(1024*1024):.1f}MB"
                            elif size > 1024:
                                size = f"{size/1024:.1f}KB"
                            else:
                                size = f"{size}B"
                        except:
                            pass

                    table.add_row(
                        str(doc.id),
                        doc.doc_type,
                        doc.source,
                        added,
                        size
                    )
                except Exception as e:
                    print(f"DEBUG: Error adding document to table: {e}")

            console.print(table)

        elif command == "remove":
            if not args:
                console.print("[red]Please specify what to remove")
                return

            if args[0] == "source":
                if len(args) < 2:
                    console.print("[red]Please specify document ID")
                    return

                try:
                    doc_id = int(args[1])
                    if doc_store.remove(doc_id):
                        console.print(f"[green]Removed document {doc_id}")
                    else:
                        console.print(f"[red]Document {doc_id} not found")
                except ValueError:
                    console.print("[red]Invalid document ID")
            else:
                console.print(f"[red]Unknown remove target: {args[0]}")
        else:
            _show_doc_help(console)

    except Exception as e:
        print(f"DEBUG: Command error: {type(e).__name__}: {e}")
        console.print(f"[red]Error: {str(e)}")

def _show_doc_help(console: Console):
    """Show document management help"""
    console.print("Document management commands:")
    console.print("  /add <file or URL> - Add document to collection")
    console.print("  /list - List all documents")
    console.print("  /remove <id> - Remove document by ID")

