"""CLI commands for document management with async support."""

from pathlib import Path
from typing import Optional
from rich.table import Table
from rich.console import Console
from rich.prompt import Confirm
from datetime import datetime
import urllib.parse
from ..storage.document_store import DocumentStore
import traceback
import logging

logger = logging.getLogger(__name__)

async def handle_doc_command(cmd: str, doc_store: DocumentStore, console: Console) -> None:
    """Handle document management commands asynchronously"""
    logger.debug(f"Handling document command: {cmd}")
    parts = cmd[1:].split()  # Remove leading slash
    if not parts:
        _show_doc_help(console)
        return

    command = parts[0].lower()
    args = parts[1:]
    logger.debug(f"Command: {command}, Args: {args}")

    try:
        if command == "add" and len(args) >= 2 and args[0] == "source":
            source = " ".join(args[1:])  # Everything after "source"
            logger.debug(f"Adding source: {source}")

            # Check if it's a URL
            try:
                parsed = urllib.parse.urlparse(source)
                if parsed.scheme and parsed.netloc:  # Valid URL
                    logger.debug(f"Treating as URL: {source}")
                    try:
                        doc = await doc_store.add_url(source)
                        console.print(f"[green]Added URL: {source}")
                    except Exception as e:
                        logger.debug(f"Error adding URL: {type(e).__name__}: {e}")
                        print(traceback.format_exc())
                        console.print(f"[red]Error adding URL: {str(e)}")
                    return
            except Exception as e:
                logger.debug(f"Not a URL: {e}")

            # Try as file path
            try:
                path = Path(source).resolve()
                logger.debug(f"Resolved path: {path}")
                
                if not path.exists():
                    logger.debug(f"File not found: {path}")
                    console.print(f"[red]File not found: {path}")
                    return
                
                logger.debug(f"File exists, attempting to add: {path}")
                try:
                    doc = await doc_store.add_file(path)
                    logger.debug(f"File added successfully with ID: {doc.id if doc else 'unknown'}")
                    console.print(f"[green]Added file: {path}")
                except Exception as e:
                    logger.debug(f"Exception adding file: {type(e).__name__}: {e}")
                    print(traceback.format_exc())
                    console.print(f"[red]Error adding file: {str(e)}")
            except Exception as e:
                logger.debug(f"Error resolving path: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                console.print(f"[red]Error with file path: {str(e)}")

        elif command == "list" and (len(args) == 0 or args[0] == "sources"):
            logger.debug("Listing sources")
            try:
                docs = doc_store.list_documents()
                logger.debug(f"Found {len(docs)} documents")

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
                        logger.debug(f"Error adding document to table: {e}")
                        print(traceback.format_exc())

                console.print(table)
            except Exception as e:
                logger.debug(f"Error listing documents: {type(e).__name__}: {e}")
                print(traceback.format_exc())
                console.print(f"[red]Error listing documents: {str(e)}")

        elif command == "remove":
            # ... rest of the original remove command code ...
            pass
        else:
            _show_doc_help(console)

    except Exception as e:
        logger.debug(f"Command error: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        console.print(f"[red]Error: {str(e)}")

def _show_doc_help(console: Console):
    """Show document management help"""
    console.print("Document management commands:")
    console.print("  /add <file or URL> - Add document to collection")
    console.print("  /list - List all documents")
    console.print("  /remove <id> - Remove document by ID")
