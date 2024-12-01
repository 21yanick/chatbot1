"""
Chat-Eingabekomponente - Verarbeitet und validiert Benutzereingaben

Diese Komponente implementiert die Eingabeschnittstelle des Chatbots mit:
- Validierung der Eingaben
- Fehlerbehandlung
- Statusanzeigen
- Performance-Tracking
"""

import streamlit as st
from typing import Callable, Awaitable
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
    Chat-Eingabekomponente mit Validierung und Statusverwaltung.
    
    Stellt ein Formular für Benutzereingaben bereit und verarbeitet
    diese mit entsprechender Validierung und Fehlerbehandlung.
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
            on_submit: Async Callback für Formulareingaben
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
            if "chat_input" not in st.session_state:
                st.session_state.chat_input = ""
            if "is_submitting" not in st.session_state:
                st.session_state.is_submitting = False
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
                st.warning("⚠️ Bitte geben Sie eine Frage ein.")
                self.logger.warning(
                    "Leere Eingabe abgelehnt",
                    extra={"session_id": st.session_state.get("session_id")}
                )
                return False
            
            # Längenbeschränkung
            if len(text) > self.max_length:
                st.warning(
                    f"⚠️ Die Frage ist zu lang. Maximal {self.max_length} "
                    "Zeichen erlaubt."
                )
                self.logger.warning(
                    "Zu lange Eingabe abgelehnt",
                    extra={
                        "session_id": st.session_state.get("session_id"),
                        "input_length": len(text),
                        "max_length": self.max_length
                    }
                )
                return False
            
            # Rate-Limiting (optional)
            if st.session_state.last_input_time:
                time_diff = (datetime.utcnow() - 
                           st.session_state.last_input_time).total_seconds()
                if time_diff < settings.chat.min_input_delay:
                    st.warning(
                        "⚠️ Bitte warten Sie einen Moment vor der "
                        "nächsten Eingabe."
                    )
                    self.logger.warning(
                        "Rate-Limit erreicht",
                        extra={
                            "session_id": st.session_state.get("session_id"),
                            "time_diff": time_diff
                        }
                    )
                    return False
            
            self.logger.debug(
                "Eingabe validiert",
                extra={
                    "input_length": len(text),
                    "session_id": st.session_state.get("session_id")
                }
            )
            return True
    
    @log_function_call(logger)
    async def _handle_submit(self) -> None:
        """
        Verarbeitet die Formularübermittlung.
        
        Validiert die Eingabe und ruft den Submit-Handler auf.
        Behandelt Fehler und aktualisiert den Eingabezustand.
        """
        text = st.session_state.chat_input.strip()
        
        try:
            with request_context():
                if self._validate_input(text):
                    with log_execution_time(self.logger, "submit_handling"):
                        try:
                            st.session_state.is_submitting = True
                            st.session_state.last_input_time = datetime.utcnow()
                            
                            # Submit-Handler aufrufen
                            await self.on_submit(text)
                            
                            self.logger.info(
                                "Nachricht erfolgreich gesendet",
                                extra={
                                    "message_length": len(text),
                                    "session_id": st.session_state.get("session_id")
                                }
                            )
                            
                        except Exception as e:
                            error_context = {
                                "message_length": len(text),
                                "session_id": st.session_state.get("session_id")
                            }
                            log_error_with_context(
                                self.logger,
                                e,
                                error_context,
                                "Fehler beim Senden der Nachricht"
                            )
                            st.error(
                                "🚫 Fehler beim Senden der Nachricht. "
                                "Bitte versuchen Sie es erneut."
                            )
                        
                        finally:
                            st.session_state.is_submitting = False
                            
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
    
    @log_function_call(logger)
    async def render(self) -> None:
        """
        Rendert die Chat-Eingabekomponente.
        
        Erstellt das Eingabeformular mit:
        - Texteingabefeld
        - Zeichenzähler
        - Submit-Button
        - Statusanzeigen
        """
        try:
            with log_execution_time(self.logger, "component_rendering"):
                with st.container():
                    # Formular mit automatischer Leerung
                    with st.form(key="chat_form", clear_on_submit=True):
                        # Texteingabefeld
                        st.text_area(
                            label="Ihre Frage",
                            key="chat_input",
                            placeholder=self.placeholder,
                            max_chars=self.max_length,
                            height=100
                        )
                        
                        # Statuszeile
                        col1, col2 = st.columns([4, 1])
                        
                        with col1:
                            current_length = len(st.session_state.chat_input)
                            st.caption(
                                f"✍️ {current_length}/{self.max_length} Zeichen"
                            )
                        
                        with col2:
                            submit_button = st.form_submit_button(
                                label="Senden" if not st.session_state.is_submitting 
                                else "Sendet...",
                                disabled=st.session_state.is_submitting,
                                use_container_width=True
                            )
                        
                        if submit_button:
                            await self._handle_submit()
            
            self.logger.debug(
                "Komponente gerendert",
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
                "Fehler beim Rendern der Komponente"
            )
            st.error(
                "🚫 Fehler beim Laden der Eingabekomponente. "
                "Bitte laden Sie die Seite neu."
            )