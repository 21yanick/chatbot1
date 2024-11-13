import streamlit as st
from typing import Optional, List
from src.backend.models.chat import Message
from src.backend.models.document import Document

class ChatMessage:
    """Component for rendering chat messages."""
    
    def __init__(self, message: Message):
        self.message = message
    
    def _render_user_message(self) -> None:
        """Render a user message."""
        with st.container():
            col1, col2 = st.columns([1, 11])
            with col1:
                st.markdown("👤")
            with col2:
                st.markdown(self.message.content)
    
    def _render_system_message(self) -> None:
        """Render a system message."""
        with st.container():
            st.markdown(f"*{self.message.content}*")
    
    def _render_assistant_message(self) -> None:
        """Render an assistant message with optional sources."""
        with st.container():
            col1, col2 = st.columns([1, 11])
            with col1:
                st.markdown("🤖")
            with col2:
                # Render main response
                st.markdown(self.message.content)
                
                # Render sources if available
                if self.message.metadata.get("context_documents"):
                    with st.expander("📚 Quellen"):
                        for doc_id in self.message.metadata["context_documents"]:
                            st.markdown(f"- Dokument: `{doc_id}`")
                
                # Render metadata if in debug mode
                if st.session_state.get("debug_mode"):
                    with st.expander("🔍 Debug Info"):
                        st.json(self.message.metadata)
    
    def _get_message_style(self) -> str:
        """Get CSS style for message based on role."""
        if self.message.role == "user":
            return """
                padding: 1rem;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
                background-color: #f0f2f6;
            """
        elif self.message.role == "assistant":
            return """
                padding: 1rem;
                border-radius: 0.5rem;
                margin-bottom: 1rem;
                background-color: #e8f0fe;
            """
        return ""
    
    def render(self) -> None:
        """Render the chat message."""
        with st.container():
            # Apply message style
            st.markdown(
                f'<div style="{self._get_message_style()}">',
                unsafe_allow_html=True
            )
            
            # Render based on role
            if self.message.role == "user":
                self._render_user_message()
            elif self.message.role == "assistant":
                self._render_assistant_message()
            elif self.message.role == "system":
                self._render_system_message()
            
            # Close style container
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Add timestamp if enabled
            if st.session_state.get("show_timestamps"):
                st.caption(
                    f"Gesendet: {self.message.timestamp.strftime('%H:%M:%S')}"
                )