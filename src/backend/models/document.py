from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class Document(BaseModel):
    """Base document model for storing content and metadata."""
    
    id: str = Field(..., description="Unique identifier for the document")
    content: str = Field(..., description="Main content of the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata for the document"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Document creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp"
    )
    source: Optional[str] = Field(
        default=None,
        description="Source of the document"
    )
    
    def update_content(self, new_content: str) -> None:
        """Update document content and updated_at timestamp."""
        self.content = new_content
        self.updated_at = datetime.utcnow()
    
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """Update document metadata and updated_at timestamp."""
        self.metadata.update(metadata)
        self.updated_at = datetime.utcnow()

    def to_embedding_format(self) -> Dict[str, Any]:
        """Convert document to format suitable for embedding storage."""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": {
                **self.metadata,
                "created_at": self.created_at.isoformat(),
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                "source": self.source
            }
        }