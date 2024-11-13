from typing import List, Optional, Dict, Any
from abc import abstractmethod

from ..models.document import Document
from .base import BaseService, ServiceError

class RetrievalServiceError(ServiceError):
    """Specific exception for retrieval service errors."""
    pass

class RetrievalService(BaseService):
    """Interface for document retrieval operations."""
    
    @abstractmethod
    async def add_document(self, document: Document) -> Document:
        """Add a document to the retrieval system."""
        pass
    
    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        pass
    
    @abstractmethod
    async def search_documents(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Search for documents based on semantic similarity.
        
        Args:
            query: The search query
            limit: Maximum number of documents to return
            metadata_filter: Optional filters for document metadata
        """
        pass
    
    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the retrieval system."""
        pass
    
    @abstractmethod
    async def update_document(
        self,
        document_id: str,
        document: Document
    ) -> Optional[Document]:
        """Update an existing document."""
        pass
    
    @abstractmethod
    async def get_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        Find documents similar to a given document.
        
        Args:
            document_id: ID of the reference document
            limit: Maximum number of similar documents to return
            score_threshold: Minimum similarity score threshold
        """
        pass