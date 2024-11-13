# tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock
import numpy as np
from src.backend.services.embedding_service import EmbeddingService

@pytest.fixture
async def embedding_service():
    """Fixture for embedding service with mocked embeddings."""
    service = EmbeddingService(model="test-model")
    
    # Mock mit dynamischer Rückgabe erstellen
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents = MagicMock(
        # Lambda-Funktion, die für jedes Eingabe-Element ein Embedding zurückgibt
        side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
    )
    
    service._embeddings = mock_embeddings
    service.initialize = AsyncMock()
    
    yield service
    await service.cleanup()