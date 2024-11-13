from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field

class Message(BaseModel):
    """Model representing a single chat message."""
    
    content: str = Field(..., description="Message content")
    role: Literal["user", "assistant", "system"] = Field(
        ..., 
        description="Role of the message sender"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Message timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata"
    )

class ChatSession(BaseModel):
    """Model representing a chat session with message history."""
    
    id: str = Field(..., description="Unique chat session identifier")
    messages: List[Message] = Field(
        default_factory=list,
        description="List of messages in the chat"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Session creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last message timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session metadata"
    )
    context_documents: List[str] = Field(
        default_factory=list,
        description="List of relevant document IDs for context"
    )
    
    def add_message(self, message: Message) -> None:
        """Add a new message to the chat session."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def get_context(self, max_messages: Optional[int] = None) -> List[Message]:
        """Get recent message context, optionally limited to max_messages."""
        if max_messages is None:
            return self.messages
        return self.messages[-max_messages:]
    
    def add_context_document(self, document_id: str) -> None:
        """Add a document ID to the context."""
        if document_id not in self.context_documents:
            self.context_documents.append(document_id)
            
    def clear_context_documents(self) -> None:
        """Clear all context documents."""
        self.context_documents.clear()