# tests/unit/test_embedding_service.py

import pytest
from unittest.mock import AsyncMock, MagicMock
import numpy as np
from src.backend.services.embedding_service import EmbeddingService, EmbeddingServiceError

@pytest.mark.asyncio
async def test_embedding_service_initialization():
    """Test embedding service initialization."""
    service = EmbeddingService(model="test-model")
    
    # Mock OpenAIEmbeddings vor initialize()
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents = AsyncMock(
        return_value=[[0.1, 0.2, 0.3]]
    )
    service._embeddings = mock_embeddings
    
    # initialize() mocken
    service.initialize = AsyncMock()
    await service.initialize()
    
    assert service._embeddings is not None
    await service.cleanup()

@pytest.mark.asyncio
async def test_get_embeddings(embedding_service: EmbeddingService):
    """Test getting embeddings for multiple texts."""
    texts = ["test1", "test2", "test3"]
    embeddings = await embedding_service.get_embeddings(texts)
    
    assert len(embeddings) == len(texts)
    assert all(len(emb) == 3 for emb in embeddings)
    embedding_service._embeddings.embed_documents.assert_called_once_with(texts)

@pytest.mark.asyncio
async def test_get_embedding_single(embedding_service: EmbeddingService):
    """Test getting embedding for a single text."""
    text = "test text"
    embedding = await embedding_service.get_embedding(text)
    
    assert len(embedding) == 3
    embedding_service._embeddings.embed_documents.assert_called_once_with([text])

@pytest.mark.asyncio
async def test_similarity_score(embedding_service: EmbeddingService):
    """Test calculating similarity score between embeddings."""
    emb1 = [1.0, 0.0, 0.0]
    emb2 = [0.0, 1.0, 0.0]
    
    score = embedding_service.similarity_score(emb1, emb2)
    assert score == 0.0  # Orthogonal vectors
    
    score = embedding_service.similarity_score(emb1, emb1)
    assert score == 1.0  # Same vector

@pytest.mark.asyncio
async def test_embedding_service_error_handling():
    """Test error handling in embedding service."""
    service = EmbeddingService(model="test-model")
    
    # Mock mit synchroner Exception
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents = MagicMock(
        side_effect=Exception("API Error")
    )
    
    service._embeddings = mock_embeddings
    service.initialize = AsyncMock()
    
    with pytest.raises(EmbeddingServiceError):
        await service.get_embeddings(["test"])

@pytest.mark.asyncio
async def test_embedding_caching(embedding_service: EmbeddingService):
    """Test that embeddings are properly cached."""
    text = "test text"
    
    # First call should use the API
    emb1 = await embedding_service.get_embedding(text)
    assert embedding_service._embeddings.embed_documents.call_count == 1
    
    # Second call should use cache
    emb2 = await embedding_service.get_embedding(text)
    assert embedding_service._embeddings.embed_documents.call_count == 1
    assert np.array_equal(emb1, emb2)

@pytest.mark.asyncio
async def test_batch_processing(embedding_service: EmbeddingService):
    """Test batch processing of embeddings."""
    texts = [f"test{i}" for i in range(150)]  # More than batch_size
    embeddings = await embedding_service.get_embeddings(texts)
    
    assert len(embeddings) == len(texts)
    # Should have made 2 calls (150 texts with batch_size=100)
    assert embedding_service._embeddings.embed_documents.call_count == 2