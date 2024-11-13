# tests/frontend/test_chat_input.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import streamlit as st
from src.frontend.components.chat.input import ChatInput

@pytest.mark.asyncio
async def test_render_components(event_loop):
    """Test rendering of input components."""
    on_submit_mock = AsyncMock()
    chat_input = ChatInput(on_submit=on_submit_mock)
    
    with patch("streamlit.form") as mock_form, \
         patch("streamlit.text_area") as mock_text_area, \
         patch("streamlit.form_submit_button") as mock_submit, \
         patch("asyncio.create_task") as mock_create_task:
            
        mock_form.return_value.__enter__ = MagicMock()
        mock_form.return_value.__exit__ = MagicMock()
        mock_submit.return_value = False  # Simulate no submit
        
        await chat_input.render()
        
        mock_form.assert_called_once()
        mock_text_area.assert_called_once()
        mock_submit.assert_called_once()

@pytest.mark.asyncio
async def test_submit_button_state(event_loop):
    """Test submit button state."""
    on_submit_mock = AsyncMock()
    chat_input = ChatInput(on_submit=on_submit_mock)
    
    with patch("streamlit.form") as mock_form, \
         patch("streamlit.form_submit_button") as mock_submit, \
         patch("asyncio.create_task") as mock_create_task:
            
        mock_form.return_value.__enter__ = MagicMock()
        mock_form.return_value.__exit__ = MagicMock()
        mock_submit.return_value = False  # Simulate no submit
        
        # Test enabled state
        st.session_state.is_submitting = False
        await chat_input.render()
        assert not mock_submit.call_args[1]["disabled"]
        
        # Test disabled state
        st.session_state.is_submitting = True
        await chat_input.render()
        assert mock_submit.call_args[1]["disabled"]