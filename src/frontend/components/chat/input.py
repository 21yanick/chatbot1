"""
Chat-Eingabekomponente - Verarbeitet und validiert Benutzereingaben

Diese Komponente implementiert die Eingabeschnittstelle des Chatbots mit:
- Streamlit Chat Input Integration
- Validierung der Eingaben
- Typing-Indikator
- Keyboard-Shortcuts
- Fehlerbehandlung
"""

import streamlit as st
from typing import Callable, Awaitable, Optional
import asyncio
from datetime import datetime

from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

# Logger für die Komponente initialisieren
logger = get_logger(__name__)

class ChatInput:
    """
    Chat-Eingabekomponente mit Streamlit Chat Integration.
    
    Implementiert ein modernes Chat-Interface mit:
    - Native Streamlit Chat-Eingabe
    - Typing-Indikator während Verarbeitung
    - Automatisches Scrollen
    - Validierung und Fehlerbehandlung
    """
    
    def __init__(
        self,
        on_submit: Callable[[str], Awaitable[None]],
        placeholder: str = "Ihre Frage...",
        max_length: int = 1000
    ):
        """
        Initialisiert die Chat-Eingabekomponente.
        
        Args:
            on_submit: Async Callback für Benutzereingaben
            placeholder: Platzhaltertext für Eingabefeld
            max_length: Maximale Eingabelänge
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.on_submit = on_submit
        self.placeholder = placeholder
        self.max_length = max_length
        
        # Eingabezustand initialisieren
        self._initialize_state()
    
    def _initialize_state(self) -> None:
        """Initialisiert den Eingabezustand wenn noch nicht vorhanden."""
        with log_execution_time(self.logger, "state_initialization"):
            if "is_typing" not in st.session_state:
                st.session_state.is_typing = False
            if "last_input_time" not in st.session_state:
                st.session_state.last_input_time = None
            
            self.logger.debug("Eingabezustand initialisiert")
    
    @log_function_call(logger)
    def _validate_input(self, text: str) -> bool:
        """
        Validiert den Eingabetext.
        
        Args:
            text: Zu validierender Text
            
        Returns:
            bool: True wenn valide, sonst False
        """
        with log_execution_time(self.logger, "input_validation"):
            # Leerzeichenprüfung
            if not text.strip():
                return False
            
            # Längenbeschränkung
            if len(text) > self.max_length:
                st.warning(
                    f"⚠️ Maximal {self.max_length} Zeichen erlaubt."
                )
                self.logger.warning(
                    "Zu lange Eingabe abgelehnt",
                    extra={
                        "input_length": len(text),
                        "max_length": self.max_length,
                        "session_id": st.session_state.get("session_id")
                    }
                )
                return False
            
            # Rate-Limiting
            if st.session_state.last_input_time:
                time_diff = (datetime.utcnow() - 
                           st.session_state.last_input_time).total_seconds()
                if time_diff < settings.chat.min_input_delay:
                    st.warning(
                        "⚠️ Bitte warten Sie einen Moment."
                    )
                    self.logger.warning(
                        "Rate-Limit erreicht",
                        extra={
                            "time_diff": time_diff,
                            "session_id": st.session_state.get("session_id")
                        }
                    )
                    return False
            
            return True
    
    def _show_typing_indicator(self) -> None:
        """Zeigt den Typing-Indikator während der Verarbeitung."""
        with st.chat_message("assistant"):
            st.markdown("Schreibt...")
            st.markdown("""
                <style>
                    .typing-indicator {
                        display: inline-flex;
                        gap: 2px;
                    }
                    .typing-indicator span {
                        width: 4px;
                        height: 4px;
                        background: currentColor;
                        border-radius: 50%;
                        animation: bounce 1.5s infinite;
                    }
                    .typing-indicator span:nth-child(2) { animation-delay: 0.1s; }
                    .typing-indicator span:nth-child(3) { animation-delay: 0.2s; }
                    @keyframes bounce {
                        0%, 60%, 100% { transform: translateY(0); }
                        30% { transform: translateY(-4px); }
                    }
                </style>
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            """, unsafe_allow_html=True)
    
    @log_function_call(logger)
    async def _handle_submit(self, message: str) -> None:
        """
        Verarbeitet die Benutzereingabe.
        
        Args:
            message: Benutzernachricht
            
        Zeigt Typing-Indikator während der Verarbeitung und
        ruft den Submit-Handler auf.
        """
        try:
            if self._validate_input(message):
                st.session_state.is_typing = True
                st.session_state.last_input_time = datetime.utcnow()
                
                self._show_typing_indicator()
                
                try:
                    await self.on_submit(message)
                    
                    self.logger.info(
                        "Nachricht erfolgreich verarbeitet",
                        extra={
                            "message_length": len(message),
                            "session_id": st.session_state.get("session_id")
                        }
                    )
                    
                except Exception as e:
                    error_context = {
                        "message_length": len(message),
                        "session_id": st.session_state.get("session_id")
                    }
                    log_error_with_context(
                        self.logger,
                        e,
                        error_context,
                        "Fehler bei Nachrichtenverarbeitung"
                    )
                    st.error(
                        "🚫 Fehler bei der Verarbeitung. "
                        "Bitte versuchen Sie es erneut."
                    )
                
                finally:
                    st.session_state.is_typing = False
                    
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Kritischer Fehler bei Eingabeverarbeitung" 
            )
            st.error(
                "🚫 Ein unerwarteter Fehler ist aufgetreten. "
                "Bitte laden Sie die Seite neu."
            )
    
    def _enable_keyboard_shortcuts(self) -> None:
        """Aktiviert Keyboard-Shortcuts für die Eingabe."""
        st.markdown("""
            <script>
                document.addEventListener('keydown', function(e) {
                    const input = document.querySelector('.stChatInput input');
                    if (!input) return;
                    
                    // STRG + ENTER zum Absenden
                    if (e.ctrlKey && e.key === 'Enter') {
                        const submitBtn = document.querySelector('[data-testid="stChatInput"] button');
                        if (submitBtn) submitBtn.click();
                    }
                    
                    // ESC zum Leeren
                    if (e.key === 'Escape') {
                        input.value = '';
                        input.focus();
                    }
                });
            </script>
        """, unsafe_allow_html=True)
    
    @log_function_call(logger)
    async def render(self) -> None:
        """
        Rendert die Chat-Eingabekomponente.
        
        Erstellt die Streamlit Chat-Eingabe mit:
        - Typing-Indikator
        - Keyboard-Shortcuts 
        - Fehlerbehandlung
        """
        try:
            with log_execution_time(self.logger, "component_rendering"):
                # Container für Chat-Eingabe
                with st.container():
                    # Native Streamlit Chat-Eingabe
                    if prompt := st.chat_input(
                        placeholder=self.placeholder,
                        max_chars=self.max_length,
                        key="chat_input"
                    ):
                        await self._handle_submit(prompt)
                
                # Keyboard-Shortcuts aktivieren
                self._enable_keyboard_shortcuts()
                
                self.logger.debug(
                    "Chat-Eingabe gerendert",
                    extra={"session_id": st.session_state.get("session_id")}
                )
            
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern der Chat-Eingabe"
            )
            st.error(
                "🚫 Fehler beim Laden der Eingabekomponente. "
                "Bitte laden Sie die Seite neu."
            )