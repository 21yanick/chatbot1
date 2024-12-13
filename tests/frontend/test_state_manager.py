"""
Test-Suite für den State Manager mit angepassten Erwartungen für die neue Service-Struktur.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import streamlit as st
from src.frontend.utils.state_manager import StateManager
from src.models.chat import Message, ChatSession

@pytest.fixture
def mock_session_state():
    """Mock Streamlit session state."""
    # Clear existing session state
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Initialize with default values
    st.session_state.initialized = False
    st.session_state.chat_history = []
    st.session_state.error = None
    
    return st.session_state

@pytest.fixture
def state_manager(mock_session_state):
    """Create a StateManager instance with mocked services."""
    with patch('src.frontend.utils.state_manager.ChatServiceImpl') as mock_chat_service:
        # Mock die Chat-Service Methoden
        mock_chat_service.return_value.initialize = AsyncMock()
        mock_chat_service.return_value.create_session = AsyncMock(return_value=ChatSession(
            id="test-session",
            messages=[],
            metadata={}
        ))
        return StateManager()

@pytest.mark.asyncio
async def test_state_manager_initialization(state_manager, mock_session_state):
    """Test StateManager initialization."""
    assert not mock_session_state.initialized
    assert isinstance(mock_session_state.chat_history, list)
    # Wir prüfen nicht mehr auf None, da wir wissen dass eine ID generiert wird
    assert isinstance(mock_session_state.session_id, str)
    assert mock_session_state.error is None

@pytest.mark.asyncio
async def test_service_initialization(state_manager, mock_session_state):
    """Test service initialization."""
    with patch('src.frontend.utils.state_manager.ChatServiceImpl') as mock_chat_service:
        mock_chat_service.return_value.initialize = AsyncMock()
        await state_manager.initialize()
        
        assert mock_session_state.initialized
        assert mock_session_state.chat_service is not None
        assert isinstance(mock_session_state.session_id, str)

@pytest.mark.asyncio
async def test_send_message(state_manager, mock_session_state):
    """Test sending a message."""
    # Setup
    await state_manager.initialize()
    
    # Mock chat service response generator
    async def mock_response_generator():
        yield "Test response chunk 1"
        yield "Test response chunk 2"
    
    mock_session_state.chat_service.get_response = AsyncMock(
        return_value=mock_response_generator()
    )
    
    # Send message
    response = await state_manager.send_message("Test message")
    
    assert response is not None
    assert len(mock_session_state.chat_history) == 2  # User message + response
    assert mock_session_state.chat_history[0].role == "user"
    assert mock_session_state.chat_history[1].role == "assistant"

@pytest.mark.asyncio
async def test_error_handling(state_manager, mock_session_state):
    """Test error handling."""
    # Setup
    await state_manager.initialize()
    
    # Mock error in chat service
    mock_session_state.chat_service.get_response = AsyncMock(
        side_effect=Exception("Test error")
    )
    
    # Send message
    response = await state_manager.send_message("Test message")
    
    assert response is None
    assert mock_session_state.error is not None
    assert "Test error" in str(mock_session_state.error)

def test_clear_chat(state_manager, mock_session_state):
    """Test clearing chat history."""
    # Add some messages
    mock_session_state.chat_history = [
        Message(content="Test 1", role="user"),
        Message(content="Test 2", role="assistant")
    ]
    
    # Clear chat
    state_manager.clear_chat()
    assert len(mock_session_state.chat_history) == 0

def test_error_management(state_manager, mock_session_state):
    """Test error management functions."""
    # Set error
    mock_session_state.error = "Test error"
    assert state_manager.has_error()
    assert state_manager.get_error() == "Test error"
    
    # Clear error
    state_manager.clear_error()
    assert not state_manager.has_error()
    assert state_manager.get_error() is None