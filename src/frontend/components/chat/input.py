import streamlit as st
from typing import Callable, Awaitable
import asyncio

class ChatInput:
    """Component for chat input with validation and submit handling."""
    
    def __init__(
        self,
        on_submit: Callable[[str], Awaitable[None]],
        placeholder: str = "Ihre Frage...",
        max_length: int = 1000
    ):
        self.on_submit = on_submit
        self.placeholder = placeholder
        self.max_length = max_length
        
        # Initialize input state
        if "chat_input" not in st.session_state:
            st.session_state.chat_input = ""
        if "is_submitting" not in st.session_state:
            st.session_state.is_submitting = False
    
    def _validate_input(self, text: str) -> bool:
        """Validate the input text."""
        if not text.strip():
            st.warning("Bitte geben Sie eine Frage ein.")
            return False
        
        if len(text) > self.max_length:
            st.warning(
                f"Die Frage ist zu lang. Maximal {self.max_length} Zeichen erlaubt."
            )
            return False
        
        return True
    
    async def _handle_submit(self) -> None:
        """Handle form submission."""
        text = st.session_state.chat_input.strip()
        
        if self._validate_input(text):
            try:
                st.session_state.is_submitting = True
                
                # Call submit handler with current text
                await self.on_submit(text)
                
            except Exception as e:
                st.error(f"Fehler beim Senden der Nachricht: {str(e)}")
            
            finally:
                st.session_state.is_submitting = False
    
    async def render(self) -> None:
        """Render the chat input component."""
        with st.container():
            # Verwende clear_on_submit=True im Formular statt manuelles Löschen
            with st.form(key="chat_form", clear_on_submit=True):
                st.text_area(
                    label="Ihre Frage",
                    key="chat_input",
                    placeholder=self.placeholder,
                    max_chars=self.max_length,
                    height=100
                )
            
                col1, col2 = st.columns([4, 1])
            
                with col1:
                    current_length = len(st.session_state.chat_input)
                    st.caption(f"{current_length}/{self.max_length} Zeichen")
            
                with col2:
                    submit_button = st.form_submit_button(
                        label="Senden",
                        disabled=st.session_state.is_submitting,
                        use_container_width=True
                    )
                
                if submit_button:
                    await self._handle_submit()