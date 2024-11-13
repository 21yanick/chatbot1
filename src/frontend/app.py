import streamlit as st
import asyncio
from typing import Optional
from src.frontend.components.chat.message import ChatMessage
from src.frontend.components.chat.input import ChatInput
from src.frontend.utils.state_manager import StateManager
from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Page config
st.set_page_config(
    page_title="Fahrzeugexperten-Chatbot",
    page_icon="🚗",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .stTextArea {
        font-size: 1rem;
    }
    .stMarkdown {
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

async def initialize_services() -> Optional[StateManager]:
    """Initialize services with error handling."""
    try:
        state_manager = StateManager()
        await state_manager.initialize()
        return state_manager
    except Exception as e:
        st.error(f"Fehler beim Initialisieren der Services: {str(e)}")
        logger.error(f"Service initialization failed: {str(e)}")
        return None

async def main():
    """Main application."""
    st.title("🚗 Fahrzeugexperten-Chatbot")
    
    # Initialize services
    state_manager = await initialize_services()
    if not state_manager:
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.markdown("### Einstellungen")
        
        # Debug mode toggle
        st.session_state.debug_mode = st.checkbox(
            "Debug-Modus",
            value=st.session_state.get("debug_mode", False)
        )
        
        # Show timestamps toggle
        st.session_state.show_timestamps = st.checkbox(
            "Zeitstempel anzeigen",
            value=st.session_state.get("show_timestamps", False)
        )
        
        # Clear chat button
        if st.button("Chat löschen", use_container_width=True):
            state_manager.clear_chat()
            st.rerun()

    
    # Main chat interface
    chat_container = st.container()
    
    with chat_container:
        # Display error if any
        if state_manager.has_error():
            st.error(state_manager.get_error())
            state_manager.clear_error()
        
        # Display chat messages
        for message in state_manager.get_messages():
            ChatMessage(message).render()
        
        # Input component
        async def on_submit(message: str):
            """Handle message submission."""
            with st.spinner("Verarbeite Anfrage..."):
                response = await state_manager.send_message(message)
                if response:
                    ChatMessage(response).render()
        
        await ChatInput(on_submit=on_submit).render()
    
    # Auto-scroll to bottom
    if st.session_state.get("chat_history"):
        js = """
        <script>
            var chatContainer = window.parent.document.querySelector('[data-testid="stVerticalBlock"]');
            chatContainer.scrollTop = chatContainer.scrollHeight;
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)

if __name__ == "__main__":
    asyncio.run(main())