from typing import List, Dict, Any, Optional
import re
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter
from ..models.document import Document
from ..interfaces.base import BaseService, ServiceError
from ..config.logging_config import get_logger

logger = get_logger(__name__)

class DocumentProcessorError(ServiceError):
    """Specific exception for document processing errors."""
    pass

class DocumentProcessor(BaseService):
    """Service for processing and chunking documents."""
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self._splitter = None
    
    async def initialize(self) -> None:
        """Initialize the document processor."""
        try:
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                is_separator_regex=r'\n\n|\n|\. |\?|\!'
            )
            logger.info("Initialized document processor")
        except Exception as e:
            raise DocumentProcessorError(f"Failed to initialize document processor: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup processor resources."""
        self._splitter = None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        return text.strip()
    
    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from document content."""
        metadata = {
            "length": len(content),
            "processed_at": datetime.utcnow().isoformat(),
            "language": self._detect_language(content),
            "topics": self._extract_topics(content)
        }
        return metadata
    
    def _detect_language(self, content: str) -> str:
        """Simple language detection."""
        # This is a simplified implementation
        # In production, use a proper language detection library
        return "de" if any(word in content.lower() for word in ["der", "die", "das", "und"]) else "en"
    
    def _extract_topics(self, content: str) -> List[str]:
        """Extract main topics from content."""
        # This is a simplified implementation
        # In production, use proper topic modeling or keyword extraction
        common_vehicle_topics = [
            "sicherheit", "parken", "elektro", "antrieb", "wartung",
            "reifen", "bremsen", "motor", "batterie", "laden"
        ]
        return [
            topic for topic in common_vehicle_topics
            if topic in content.lower()
        ]
    
    async def process_document(
        self,
        document: Document,
        update_metadata: bool = True
    ) -> List[Document]:
        """
        Process a document and split it into chunks.
        
        Args:
            document: The document to process
            update_metadata: Whether to update document metadata
        
        Returns:
            List of processed document chunks
        """
        if not self._splitter:
            raise DocumentProcessorError("Document processor not initialized")
        
        try:
            # Clean content
            cleaned_content = self._clean_text(document.content)
            
            # Split into chunks
            chunks = self._splitter.split_text(cleaned_content)
            
            # Filter out too small chunks
            chunks = [chunk for chunk in chunks if len(chunk) >= self.min_chunk_size]
            
            # Create document chunks
            doc_chunks = []
            for i, chunk in enumerate(chunks):
                chunk_metadata = {
                    "original_id": document.id,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                
                if update_metadata:
                    chunk_metadata.update(self._extract_metadata(chunk))
                
                if document.metadata:
                    chunk_metadata.update(document.metadata)
                
                doc_chunks.append(Document(
                    id=f"{document.id}_chunk_{i}",
                    content=chunk,
                    metadata=chunk_metadata,
                    source=document.source,
                    created_at=document.created_at
                ))
            
            logger.info(
                f"Processed document {document.id} into {len(doc_chunks)} chunks"
            )
            return doc_chunks
        
        except Exception as e:
            raise DocumentProcessorError(
                f"Failed to process document {document.id}: {str(e)}"
            )
    
    async def validate_document(self, document: Document) -> bool:
        """
        Validate document content and structure.
        
        Args:
            document: The document to validate
        
        Returns:
            True if document is valid, False otherwise
        """
        try:
            if not document.content or len(document.content.strip()) < self.min_chunk_size:
                logger.warning(f"Document {document.id} content too short")
                return False
            
            if len(document.content) > 1_000_000:  # 1MB limit
                logger.warning(f"Document {document.id} content too large")
                return False
            
            # Add more validation rules as needed
            return True
        
        except Exception as e:
            logger.error(f"Document validation failed: {str(e)}")
            return False