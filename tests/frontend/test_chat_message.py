# tests/frontend/test_chat_message.py
import pytest
from unittest.mock import patch, MagicMock
import streamlit as st
from src.frontend.components.chat.message import ChatMessage
from src.backend.models.chat import Message

@pytest.mark.asyncio
async def test_system_message_rendering():
    """Test rendering of system messages."""
    system_message = Message(
        content="Test system message",
        role="system"
    )
    
    chat_message = ChatMessage(system_message)
    
    with patch("streamlit.markdown") as mock_markdown, \
         patch("streamlit.container") as mock_container:
        
        mock_container.return_value.__enter__ = MagicMock()
        mock_container.return_value.__exit__ = MagicMock()
        
        chat_message.render()  # Remove await if render is not async
        
        # Verify the system message was rendered correctly
        mock_markdown.assert_any_call("*Test system message*")