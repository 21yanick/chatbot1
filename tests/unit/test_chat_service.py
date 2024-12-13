"""
Test-Suite für den Chat-Service und seine Manager-Komponenten.
Testet sowohl die einzelnen Manager als auch deren Zusammenspiel.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from src.backend.services.chat.chat_service import ChatServiceImpl
from src.backend.services.chat.managers.session_manager import SessionManager
from src.backend.services.chat.managers.context_manager import ContextManager
from src.backend.services.chat.managers.prompt_manager import PromptManager
from src.models.chat import Message, ChatSession
from src.models.document import Document
from src.backend.interfaces.chat import ChatServiceError

@pytest.fixture
async def mock_llm():
    """Fixture für ein Mock LLM."""
    async def mock_stream(*args, **kwargs):
        yield "This is "
        yield "a test "
        yield "response."
    
    mock = AsyncMock()
    mock.astream.return_value = mock_stream()
    return mock

@pytest.fixture
async def chat_service(mock_llm):
    """Fixture für einen konfigurierten ChatService mit gemockten Komponenten."""
    retrieval_service = AsyncMock()
    retrieval_service.initialize = AsyncMock()
    retrieval_service.get_document = AsyncMock(return_value=Document(
        id="test_doc",
        content="Test content",
        metadata={"type": "test"}
    ))
    
    with patch('langchain_openai.ChatOpenAI', return_value=mock_llm):
        service = ChatServiceImpl(
            retrieval_service=retrieval_service,
            model_name="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=1000
        )
        await service.initialize()
        return service

@pytest.fixture
def mock_session():
    """Fixture für eine Mock-Session."""
    return ChatSession(
        id="test_session",
        messages=[
            Message(content="System message", role="system"),
            Message(content="User message", role="user"),
            Message(content="Assistant message", role="assistant")
        ],
        metadata={}
    )

@pytest.mark.asyncio
async def test_chat_service_initialization(chat_service):
    """Test der Service-Initialisierung."""
    assert chat_service._llm is not None
    assert isinstance(chat_service.session_manager, SessionManager)
    assert isinstance(chat_service.context_manager, ContextManager)
    assert isinstance(chat_service.prompt_manager, PromptManager)

@pytest.mark.asyncio
async def test_session_management(chat_service):
    """Test der Session-Verwaltungsfunktionen."""
    # Session erstellen
    session = await chat_service.create_session()
    assert session.id is not None
    
    # Session abrufen
    retrieved = await chat_service.get_session(session.id)
    assert retrieved.id == session.id
    
    # Metadaten aktualisieren
    metadata = {"test_key": "test_value"}
    updated = await chat_service.update_session_metadata(session.id, metadata)
    assert updated.metadata["test_key"] == "test_value"
    
    # Session löschen
    deleted = await chat_service.delete_session(session.id)
    assert deleted is True
    
    # Gelöschte Session abrufen
    none_session = await chat_service.get_session(session.id)
    assert none_session is None

@pytest.mark.asyncio
async def test_manager_interaction(chat_service):
    """Test der Interaktion zwischen den Managern."""
    session = await chat_service.create_session()
    
    # PromptManager Test
    custom_prompt = "Custom test prompt template"
    chat_service.prompt_manager.add_template("custom", custom_prompt)
    assert chat_service.prompt_manager.get_template("custom") == custom_prompt
    
    # ContextManager Test
    documents = [Document(id="1", content="Test", metadata={})]
    context = chat_service.context_manager.prepare_document_context(documents)
    assert "Test" in context
    
    # SessionManager mit Context
    message = Message(content="Test message", role="user")
    updated_session = await chat_service.session_manager.add_message(session.id, message)
    assert len(updated_session.messages) > 0

@pytest.mark.asyncio
async def test_get_response_basic(chat_service):
    """Test der grundlegenden Antwortgenerierung."""
    query = "Test question"
    responses = []
    
    async for chunk in chat_service.get_response(query):
        assert isinstance(chunk, str)
        responses.append(chunk)
    
    assert len(responses) > 0
    assert all(isinstance(r, str) for r in responses)
    complete_response = "".join(responses)
    assert "test response" in complete_response.lower()

@pytest.mark.asyncio
async def test_get_response_with_context(chat_service):
    """Test der Antwortgenerierung mit Kontext."""
    query = "Test question with context"
    context_docs = [
        Document(
            id="doc1",
            content="Relevant test content",
            metadata={"type": "test"}
        )
    ]
    
    responses = []
    async for chunk in chat_service.get_response(
        query=query,
        context_docs=context_docs
    ):
        responses.append(chunk)
    
    assert len(responses) > 0
    complete_response = "".join(responses)
    assert len(complete_response) > 0

@pytest.mark.asyncio
async def test_get_response_with_session(chat_service, mock_session):
    """Test der Antwortgenerierung mit existierender Session."""
    # Session vorbereiten
    await chat_service.session_manager.create_session(
        session_id=mock_session.id,
        metadata=mock_session.metadata
    )
    
    query = "Follow-up question"
    responses = []
    
    async for chunk in chat_service.get_response(
        query=query,
        session_id=mock_session.id
    ):
        responses.append(chunk)
    
    assert len(responses) > 0
    retrieved_session = await chat_service.get_session(mock_session.id)
    assert len(retrieved_session.messages) > len(mock_session.messages)

@pytest.mark.asyncio
async def test_error_handling(chat_service):
    """Test der Fehlerbehandlung."""
    # Test mit ungültiger Session
    with pytest.raises(ChatServiceError):
        async for _ in chat_service.get_response(
            query="Test question",
            session_id="non_existent_session"
        ):
            pass
    
    # Test mit ungültigem Kontext
    with pytest.raises(ChatServiceError):
        async for _ in chat_service.get_response(
            query="Test question",
            context_docs=[Document(id="invalid", content="")]
        ):
            pass

@pytest.mark.asyncio
async def test_cleanup(chat_service):
    """Test der Ressourcenbereinigung."""
    await chat_service.cleanup()
    assert chat_service._llm is None

@pytest.mark.asyncio
async def test_context_length_limits(chat_service):
    """Test der Kontextlängenbegrenzungen."""
    # Erstelle eine Session mit vielen Nachrichten
    session = await chat_service.create_session()
    for i in range(20):  # Mehr als max_context_messages
        message = Message(
            content=f"Test message {i}",
            role="user" if i % 2 == 0 else "assistant"
        )
        await chat_service.session_manager.add_message(session.id, message)
    
    responses = []
    async for chunk in chat_service.get_response(
        query="Test with long history",
        session_id=session.id
    ):
        responses.append(chunk)
    
    assert len(responses) > 0

@pytest.mark.asyncio
async def test_concurrent_requests(chat_service):
    """Test der gleichzeitigen Anfragen."""
    import asyncio
    
    async def make_request(query: str):
        responses = []
        async for chunk in chat_service.get_response(query):
            responses.append(chunk)
        return "".join(responses)
    
    # Mehrere Anfragen gleichzeitig ausführen
    queries = ["Query 1", "Query 2", "Query 3"]
    tasks = [make_request(q) for q in queries]
    responses = await asyncio.gather(*tasks)
    
    assert len(responses) == len(queries)
    assert all(len(r) > 0 for r in responses)