# src/backend/services/embedding_service.py

from typing import List, Dict, Any, Optional
import asyncio
from functools import lru_cache
import numpy as np
from langchain_openai import OpenAIEmbeddings
from ..interfaces.base import BaseService, ServiceError
from ..config.settings import settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)

class EmbeddingCache:
    """Simple cache implementation for embeddings."""
    def __init__(self, max_size: int = 10000):
        self.cache: Dict[str, List[float]] = {}
        self.max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[List[float]]:
        """Get embedding from cache."""
        async with self._lock:
            return self.cache.get(key)

    async def set(self, key: str, value: List[float]) -> None:
        """Set embedding in cache."""
        async with self._lock:
            if len(self.cache) >= self.max_size:
                # Remove oldest item if cache is full
                self.cache.pop(next(iter(self.cache)))
            self.cache[key] = value

    def clear(self) -> None:
        """Clear the cache."""
        self.cache.clear()

class EmbeddingServiceError(ServiceError):
    """Specific exception for embedding service errors."""
    pass

class EmbeddingService(BaseService):
    """Service for generating and managing embeddings."""
    
    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        batch_size: int = 100,
        cache_size: int = 10000,
        embeddings = None
    ):
        self.model = model
        self.batch_size = batch_size
        self._embeddings = embeddings
        self._cache = EmbeddingCache(max_size=cache_size)
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the embedding service."""
        try:
            if not self._embeddings:
                self._embeddings = OpenAIEmbeddings(
                    model=self.model
                )
            logger.info(f"Initialized embedding service with model: {self.model}")
        except Exception as e:
            raise EmbeddingServiceError(f"Failed to initialize embedding service: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        self._embeddings = None
        self._cache.clear()

    async def get_embeddings(
        self,
        texts: List[str],
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ) -> List[List[float]]:
        """Get embeddings for a list of texts with retry logic."""
        if not self._embeddings:
            raise EmbeddingServiceError("Embedding service not initialized")
        
        async with self._lock:
            try:
                # Check cache first
                cached_results = []
                missing_indices = []
                
                for i, text in enumerate(texts):
                    cached = await self._cache.get(text)
                    if cached is not None:
                        cached_results.append(cached)
                    else:
                        cached_results.append(None)
                        missing_indices.append(i)
                
                if not missing_indices:
                    return [r for r in cached_results if r is not None]
                
                # Process missing embeddings in batches
                missing_texts = [texts[i] for i in missing_indices]
                all_embeddings = []
                
                for i in range(0, len(missing_texts), self.batch_size):
                    batch = missing_texts[i:i + self.batch_size]
                    for attempt in range(retry_attempts):
                        try:
                            # Direkt die synchrone Methode aufrufen
                            batch_embeddings = self._embeddings.embed_documents(batch)
                            all_embeddings.extend(batch_embeddings)
                            break
                        except Exception as e:
                            if attempt == retry_attempts - 1:
                                raise EmbeddingServiceError(
                                    f"Failed to get embeddings after {retry_attempts} attempts: {str(e)}"
                                )
                            logger.warning(
                                f"Embedding attempt {attempt + 1} failed, retrying..."
                            )
                            await asyncio.sleep(retry_delay * (attempt + 1))
                
                # Update cache and results
                for i, embedding in zip(missing_indices, all_embeddings):
                    await self._cache.set(texts[i], embedding)
                    cached_results[i] = embedding
                
                return [r for r in cached_results if r is not None]
                
            except Exception as e:
                raise EmbeddingServiceError(f"Failed to get embeddings: {str(e)}")

    async def get_embedding(
        self,
        text: str,
        retry_attempts: int = 3
    ) -> List[float]:
        """Get embedding for a single text."""
        embeddings = await self.get_embeddings([text], retry_attempts)
        return embeddings[0]
    
    def similarity_score(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        try:
            a = np.array(embedding1)
            b = np.array(embedding2)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        except Exception as e:
            raise EmbeddingServiceError(
                f"Failed to calculate similarity score: {str(e)}"
            )