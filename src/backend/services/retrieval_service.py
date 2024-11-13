# src/backend/services/retrieval_service.py

from typing import List, Dict, Any, Optional
import asyncio
from functools import lru_cache
from ..models.document import Document
from ..interfaces.retrieval import RetrievalService, RetrievalServiceError
from .embedding_service import EmbeddingService
from .document_processor import DocumentProcessor
from ..utils.database import ChromaDBManager
from ..config.logging_config import get_logger

logger = get_logger(__name__)

class RetrievalServiceImpl(RetrievalService):
    """Implementation of the retrieval service using ChromaDB."""
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        document_processor: DocumentProcessor,
        cache_size: int = 1000
    ):
        self.embedding_service = embedding_service
        self.document_processor = document_processor
        self.db = ChromaDBManager()
        self._document_cache = {}
        self._cache_lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the retrieval service and its dependencies."""
        try:
            await self.embedding_service.initialize()
            await self.document_processor.initialize()
            await self.db.initialize()
            logger.info("Initialized retrieval service")
        except Exception as e:
            raise RetrievalServiceError(f"Failed to initialize retrieval service: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        try:
            await self.embedding_service.cleanup()
            await self.document_processor.cleanup()
            await self.db.cleanup()
            self._document_cache.clear()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    @lru_cache(maxsize=100)
    def _get_cached_document(self, document_id: str) -> Optional[Document]:
        """Get document from cache."""
        return self._document_cache.get(document_id)
    
    async def get_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """Find documents similar to a given document."""
        try:
            document = await self.get_document(document_id)
            if not document:
                return []
            
            # Use the document content as query
            similar_docs = await self.search_documents(
                query=document.content,
                limit=limit + 1  # Add 1 to account for the document itself
            )
            
            # Remove the original document from results if present
            return [doc for doc in similar_docs if doc.id != document_id]
        except Exception as e:
            raise RetrievalServiceError(f"Failed to get similar documents: {str(e)}")
    
    async def add_document(self, document: Document) -> Document:
        """Add a document to the retrieval system."""
        try:
            # Process document and add to database
            chunks = await self.document_processor.process_document(document)
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedding_service.get_embeddings(chunk_texts)
            
            # Store in ChromaDB
            await self.db.add_documents(
                ids=[chunk.id for chunk in chunks],
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=[chunk.metadata for chunk in chunks]
            )
            
            # Update cache
            async with self._cache_lock:
                self._document_cache[document.id] = document
                for chunk in chunks:
                    self._document_cache[chunk.id] = chunk
            
            logger.info(f"Added document {document.id} with {len(chunks)} chunks")
            return document
            
        except Exception as e:
            raise RetrievalServiceError(f"Failed to add document: {str(e)}")
    
    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        try:
            # Check cache first
            cached_doc = self._get_cached_document(document_id)
            if cached_doc:
                return cached_doc
            
            # Query database
            results = await self.db.query(
                query_embeddings=[],  # Empty for metadata-only query
                where={"original_id": document_id}
            )
            
            if not results or not results.get("documents"):
                return None
            
            # Reconstruct document
            document = await self._reconstruct_document(results, document_id)
            
            # Update cache
            async with self._cache_lock:
                self._document_cache[document_id] = document
            
            return document
            
        except Exception as e:
            raise RetrievalServiceError(f"Failed to get document: {str(e)}")
    
    async def search_documents(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """Search for documents based on semantic similarity."""
        try:
            query_embedding = await self.embedding_service.get_embedding(query)
            results = await self.db.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=metadata_filter
            )
            
            if not results or not results.get("documents"):
                return []
            
            return await self._process_search_results(results)
            
        except Exception as e:
            raise RetrievalServiceError(f"Failed to search documents: {str(e)}")
    
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document from the retrieval system."""
        try:
            document = await self.get_document(document_id)
            if not document:
                return False
            
            # Delete chunks
            chunk_ids = [
                f"{document_id}_chunk_{i}"
                for i in range(document.metadata.get("total_chunks", 1))
            ]
            await self.db.delete(chunk_ids)
            
            # Clear cache
            async with self._cache_lock:
                self._document_cache.pop(document_id, None)
                for chunk_id in chunk_ids:
                    self._document_cache.pop(chunk_id, None)
            
            logger.info(f"Deleted document {document_id}")
            return True
            
        except Exception as e:
            raise RetrievalServiceError(f"Failed to delete document: {str(e)}")
    
    async def update_document(
        self,
        document_id: str,
        document: Document
    ) -> Optional[Document]:
        """Update an existing document."""
        try:
            await self.delete_document(document_id)
            return await self.add_document(document)
        except Exception as e:
            raise RetrievalServiceError(f"Failed to update document: {str(e)}")
    
    async def _reconstruct_document(
        self,
        results: Dict[str, Any],
        document_id: str
    ) -> Document:
        """Helper method to reconstruct a document from chunks."""
        chunks = []
        for i, (doc_id, content, metadata) in enumerate(zip(
            results["ids"],
            results["documents"],
            results["metadatas"]
        )):
            chunk = Document(
                id=doc_id,
                content=content,
                metadata=metadata,
                created_at=metadata.get("created_at")
            )
            chunks.append(chunk)
        
        # Sort and combine chunks
        chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
        combined_content = " ".join(chunk.content for chunk in chunks)
        
        # Create document
        metadata = chunks[0].metadata.copy()
        metadata.pop("chunk_index", None)
        metadata.pop("total_chunks", None)
        
        return Document(
            id=document_id,
            content=combined_content,
            metadata=metadata,
            created_at=chunks[0].created_at
        )
    
    async def _process_search_results(
        self,
        results: Dict[str, Any]
    ) -> List[Document]:
        """Helper method to process search results."""
        documents = []
        for i, (doc_id, content, metadata) in enumerate(zip(
            results["ids"],
            results["documents"],
            results["metadatas"]
        )):
            original_id = metadata.get("original_id", doc_id)
            if original_id != doc_id:
                doc = await self.get_document(original_id)
                if doc:
                    documents.append(doc)
            else:
                doc = Document(
                    id=doc_id,
                    content=content,
                    metadata=metadata,
                    created_at=metadata.get("created_at")
                )
                documents.append(doc)
        return documents