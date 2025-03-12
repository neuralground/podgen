#!/usr/bin/env python3
"""
Direct CLI command for adding documents.
Save this file as fix_doc_commands.py and run it with python fix_doc_commands.py
"""

import asyncio
import sys
from pathlib import Path
from rich.console import Console
from podgen.storage.document_store import DocumentStore

async def add_document(file_path: str):
    """Add a document directly using DocumentStore."""
    console = Console()
    console.print(f"Adding document: {file_path}")
    
    try:
        # Create document store
        doc_store = DocumentStore(Path.home() / ".podgen/data/documents.db")
        console.print("Document store initialized")
        
        # Resolve path
        path = Path(file_path).resolve()
        console.print(f"Resolved path: {path}")
        
        if not path.exists():
            console.print(f"[red]Error: File does not exist: {path}")
            return
        
        # Add file
        console.print(f"Adding file to document store...")
        doc = await doc_store.add_file(path)
        console.print(f"[green]Successfully added document with ID: {doc.id}")
        
        # Show document info
        console.print("\nDocument details:")
        console.print(f"ID: {doc.id}")
        console.print(f"Source: {doc.source}")
        console.print(f"Type: {doc.doc_type}")
        console.print(f"Content length: {len(doc.content) if doc.content else 0} characters")
        
    except Exception as e:
        console.print(f"[red]Error: {type(e).__name__}: {e}")
        import traceback
        console.print(traceback.format_exc())

async def list_documents():
    """List all documents directly using DocumentStore."""
    console = Console()
    console.print("Listing all documents")
    
    try:
        # Create document store
        doc_store = DocumentStore(Path.home() / ".podgen/data/documents.db")
        
        # List documents
        docs = doc_store.list_documents()
        console.print(f"Found {len(docs)} documents")
        
        if not docs:
            console.print("No documents in the collection")
            return
        
        # Display documents
        for doc in docs:
            console.print(f"ID: {doc.id}, Title: {doc.title}, Type: {doc.doc_type}")
        
    except Exception as e:
        console.print(f"[red]Error: {type(e).__name__}: {e}")
        import traceback
        console.print(traceback.format_exc())

def show_help():
    """Show help information."""
    console = Console()
    console.print("Document Command Utility")
    console.print("Commands:")
    console.print("  add <file_path>  - Add a document")
    console.print("  list             - List all documents")
    console.print("  help             - Show this help")

async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "add" and len(sys.argv) > 2:
        await add_document(sys.argv[2])
    elif command == "list":
        await list_documents()
    else:
        show_help()

if __name__ == "__main__":
    asyncio.run(main())

