from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api import Collection
from contextlib import asynccontextmanager
from ..config.settings import settings

class DatabaseError(Exception):
    """Base exception for database-related errors."""
    pass

class ChromaDBManager:
    """Manager for ChromaDB operations."""
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        self.persist_directory = persist_directory or settings.database.persist_directory
        self.collection_name = collection_name or settings.database.collection_name
        self._client = None
        self._collection = None
    
    async def initialize(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            raise DatabaseError(f"Failed to initialize ChromaDB: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup database resources."""
        self._client = None
        self._collection = None
    
    @property
    def collection(self) -> Collection:
        """Get the current collection."""
        if self._collection is None:
            raise DatabaseError("Database not initialized")
        return self._collection
    
    async def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Add documents to the collection."""
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
        except Exception as e:
            raise DatabaseError(f"Failed to add documents: {str(e)}")
    
    async def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the collection using embeddings."""
        try:
            return self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where
            )
        except Exception as e:
            raise DatabaseError(f"Failed to query documents: {str(e)}")
    
    async def delete(self, ids: List[str]) -> None:
        """Delete documents by IDs."""
        try:
            self.collection.delete(ids=ids)
        except Exception as e:
            raise DatabaseError(f"Failed to delete documents: {str(e)}")
    
    async def update(
        self,
        id: str,
        embedding: List[float],
        document: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update a document."""
        try:
            self.collection.update(
                ids=[id],
                embeddings=[embedding],
                documents=[document],
                metadatas=[metadata] if metadata else None
            )
        except Exception as e:
            raise DatabaseError(f"Failed to update document: {str(e)}")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions."""
        try:
            yield self
        except Exception as e:
            raise DatabaseError(f"Transaction failed: {str(e)}")