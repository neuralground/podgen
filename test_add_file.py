#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from podgen.storage.document_store import DocumentStore

async def main():
    print("Starting test script")
    
    # Get the file path from command line or use default
    file_path = sys.argv[1] if len(sys.argv) > 1 else "../test.pdf"
    pdf_path = Path(file_path).resolve()
    print(f"Testing with file: {pdf_path}")
    print(f"File exists: {pdf_path.exists()}")
    
    # Initialize document store
    doc_store = DocumentStore(Path("./test_documents.db"))
    print("Document store initialized")
    
    try:
        # Try to add the file
        print(f"Attempting to add file: {pdf_path}")
        doc = await doc_store.add_file(pdf_path)
        print(f"Successfully added document with ID: {doc.id}")
        print(f"Content length: {len(doc.content) if doc.content else 0}")
    except Exception as e:
        print(f"Error adding file: {type(e).__name__}: {e}")
    
    # List documents
    print("\nListing documents:")
    docs = doc_store.list_documents()
    for doc in docs:
        print(f"ID: {doc.id}, Source: {doc.source}")

if __name__ == "__main__":
    asyncio.run(main())

