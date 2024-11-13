from typing import List, Optional, Dict, Any
from abc import abstractmethod

from ..models.chat import ChatSession, Message
from .base import BaseService, ServiceError

class ChatServiceError(ServiceError):
    """Specific exception for chat service errors."""
    pass

class ChatService(BaseService):
    """Interface for chat-related operations."""
    
    @abstractmethod
    async def create_session(
        self, 
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """Create a new chat session."""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Retrieve a chat session by ID."""
        pass
    
    @abstractmethod
    async def add_message(
        self, 
        session_id: str, 
        message: Message,
        update_context: bool = True
    ) -> ChatSession:
        """
        Add a message to a chat session.
        
        Args:
            session_id: The ID of the session to add the message to
            message: The message to add
            update_context: Whether to update the context documents based on the message
        """
        pass
    
    @abstractmethod
    async def get_context(
        self, 
        session_id: str, 
        max_messages: Optional[int] = None,
        include_system: bool = True
    ) -> List[Message]:
        """
        Get the conversation context for a session.
        
        Args:
            session_id: The ID of the session to get context from
            max_messages: Maximum number of messages to return
            include_system: Whether to include system messages
        """
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        pass
    
    @abstractmethod
    async def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """Update session metadata."""
        pass