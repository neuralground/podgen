import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages HTTP session lifecycle."""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the current session if it exists."""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            finally:
                self._session = None

    async def __aenter__(self) -> 'SessionManager':
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
