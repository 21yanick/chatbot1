# tests/conftest.py
import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np
import asyncio
import streamlit as st

# Umgebungsvariablen Setup
os.environ.update({
    "OPENAI_API_KEY": "test-key",
    "CHAT__MAX_CONTEXT_MESSAGES": "10",
    "CHAT__SYSTEM_PROMPT": "Test prompt",
    "DATABASE__PERSIST_DIRECTORY": "./test/data/chromadb",
    "DATABASE__COLLECTION_NAME": "test_documents",
    "ENVIRONMENT": "test",
    "LOG_LEVEL": "DEBUG"
})

@pytest.fixture(scope="function")
async def embedding_service():
    """Fixture for embedding service with mocked embeddings."""
    from src.backend.services.embedding_service import EmbeddingService
    
    service = EmbeddingService(model="test-model")
    mock_embeddings = MagicMock()
    mock_embeddings.embed_documents = MagicMock(
        side_effect=lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
    )
    service._embeddings = mock_embeddings
    await service.initialize()
    
    yield service
    
    await service.cleanup()

@pytest.fixture(autouse=True)
def setup_streamlit():
    """Setup Streamlit session state for testing."""
    # Clear session state before each test
    for key in list(st.session_state.keys()):
        del st.session_state[key]

@pytest.fixture
def event_loop():
    """Create event loop for each test."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()