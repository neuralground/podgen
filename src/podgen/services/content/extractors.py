from abc import ABC, abstractmethod
from pathlib import Path
import logging
from typing import Optional, Dict, Any
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import PyPDF2
import json
import csv
from io import StringIO
import markdown
import docx
import mimetypes
import tempfile

logger = logging.getLogger(__name__)

class ContentExtractor(ABC):
    """Base class for content extractors."""
    
    @abstractmethod
    async def extract(self, source: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract content from source."""
        pass
    
    @abstractmethod
    def supports(self, source: str) -> bool:
        """Check if this extractor supports the given source."""
        pass

class TextExtractor(ContentExtractor):
    """Extracts content from plain text files."""
    
    def supports(self, source: str) -> bool:
        if Path(source).is_file():
            return Path(source).suffix.lower() in ['.txt', '.md', '.csv', '.json']
        return False
    
    async def extract(self, source: str, metadata: Dict[str, Any]) -> Optional[str]:
        try:
            path = Path(source)
            if not path.exists():
                logger.error(f"File not found: {source}")
                return None
                
            content = path.read_text(encoding='utf-8')
            
            # Handle different text formats
            if path.suffix.lower() == '.md':
                # Convert markdown to plain text
                content = markdown.markdown(content)
                content = BeautifulSoup(content, 'html.parser').get_text()
                
            elif path.suffix.lower() == '.csv':
                # Parse CSV and convert to readable text
                reader = csv.DictReader(StringIO(content))
                rows = list(reader)
                if rows:
                    # Create summary of CSV content
                    headers = list(rows[0].keys())
                    summary = f"CSV data with {len(rows)} rows and columns: {', '.join(headers)}\n\n"
                    
                    # Add sample of data
                    sample_size = min(5, len(rows))
                    summary += f"Sample of {sample_size} rows:\n"
                    for row in rows[:sample_size]:
                        summary += f"- {', '.join(str(v) for v in row.values())}\n"
                    content = summary
                    
            elif path.suffix.lower() == '.json':
                # Parse JSON and convert to readable text
                data = json.loads(content)
                content = json.dumps(data, indent=2)
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from {source}: {e}")
            return None

class PDFExtractor(ContentExtractor):
    """Extracts content from PDF files."""
    
    def supports(self, source: str) -> bool:
        return Path(source).suffix.lower() == '.pdf'
    
    async def extract(self, source: str, metadata: Dict[str, Any]) -> Optional[str]:
        try:
            with open(source, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                # Extract metadata
                info = reader.metadata
                if info:
                    metadata.update({
                        'title': info.get('/Title', ''),
                        'author': info.get('/Author', ''),
                        'subject': info.get('/Subject', ''),
                        'keywords': info.get('/Keywords', '')
                    })
                
                # Extract text from all pages
                content = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        content.append(text.strip())
                
                return '\n\n'.join(content)
                
        except Exception as e:
            logger.error(f"Error extracting PDF content from {source}: {e}")
            return None

class DocxExtractor(ContentExtractor):
    """Extracts content from Word documents."""
    
    def supports(self, source: str) -> bool:
        return Path(source).suffix.lower() in ['.docx', '.doc']
    
    async def extract(self, source: str, metadata: Dict[str, Any]) -> Optional[str]:
        try:
            doc = docx.Document(source)
            
            # Extract document properties
            core_props = doc.core_properties
            metadata.update({
                'title': core_props.title or '',
                'author': core_props.author or '',
                'created': core_props.created.isoformat() if core_props.created else '',
                'modified': core_props.modified.isoformat() if core_props.modified else ''
            })
            
            # Extract text from paragraphs
            content = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    content.append(text)
            
            return '\n\n'.join(content)
            
        except Exception as e:
            logger.error(f"Error extracting Word document content from {source}: {e}")
            return None

class WebExtractor(ContentExtractor):
    """Extracts content from web pages."""
    
    def __init__(self):
        self.session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def supports(self, source: str) -> bool:
        try:
            return source.startswith(('http://', 'https://'))
        except:
            return False
    
    async def extract(self, source: str, metadata: Dict[str, Any]) -> Optional[str]:
        try:
            session = await self._get_session()
            
            async with session.get(source) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch {source}: {response.status}")
                    return None
                
                content_type = response.headers.get('content-type', '').lower()
                
                # Handle different content types
                if 'text/html' in content_type:
                    html = await response.text()
                    return await self._extract_article_content(html, metadata)
                    
                elif 'application/pdf' in content_type:
                    # Download PDF and process with PDF extractor
                    data = await response.read()
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = tmp.name
                    
                    try:
                        pdf_extractor = PDFExtractor()
                        content = await pdf_extractor.extract(tmp_path, metadata)
                        return content
                    finally:
                        Path(tmp_path).unlink()
                        
                else:
                    # For other content types, just get raw text
                    return await response.text()
                    
        except Exception as e:
            logger.error(f"Error extracting web content from {source}: {e}")
            return None
        
    async def _extract_article_content(self, html: str, metadata: Dict[str, Any]) -> str:
        """Extract main article content from HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract metadata
        metadata.update({
            'title': soup.title.string if soup.title else '',
            'description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else ''
        })
        
        # Remove unwanted elements
        for elem in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        # Try to find main content
        main_content = None
        
        # Check for article tag
        if soup.find('article'):
            main_content = soup.find('article')
        
        # Check for common content div IDs
        elif soup.find('div', {'id': ['content', 'main-content', 'article-content']}):
            main_content = soup.find('div', {'id': ['content', 'main-content', 'article-content']})
        
        # Fall back to body
        if not main_content:
            main_content = soup.body
        
        if main_content:
            # Extract text from paragraphs
            paragraphs = []
            for p in main_content.find_all('p'):
                text = p.get_text().strip()
                if text:
                    paragraphs.append(text)
            
            return '\n\n'.join(paragraphs)
        
        return ''

