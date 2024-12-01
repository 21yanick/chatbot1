"""
Chat-Nachrichtenkomponente - Rendert verschiedene Nachrichtentypen

Diese Komponente ist verantwortlich für die visuelle Darstellung von:
- Benutzernachrichten
- Systemnachrichten 
- Assistentenantworten
inkl. Metadaten, Quellen und Debug-Informationen
"""

import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.backend.models.chat import Message
from src.backend.models.document import Document
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

class ChatMessage:
    """
    Komponente zur Darstellung von Chat-Nachrichten.
    
    Unterstützt verschiedene Nachrichtentypen und bietet
    kontextabhängige Darstellungsoptionen mit den neuen
    Streamlit Chat-Elementen.
    """
    
    def __init__(self, message: Message):
        """
        Initialisiert die Nachrichtenkomponente.
        
        Args:
            message: Darzustellende Nachricht
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.message = message

    @log_function_call(logger)
    def _render_user_message(self) -> None:
        """
        Rendert eine Benutzernachricht.
        
        Stellt die Nachricht mit Benutzer-Avatar und entsprechendem
        Styling im ChatGPT-Stil dar.
        """
        try:
            with st.chat_message("user", avatar="👤"):
                # Hauptnachricht
                st.markdown(self.message.content)
                
                # Zeitstempel
                if st.session_state.get("show_timestamps"):
                    st.caption(
                        f"⏰ {self.message.timestamp.strftime('%H:%M')}"
                    )
                
                # Debug-Informationen
                if st.session_state.get("debug_mode"):
                    with st.expander("🔍 Debug Info"):
                        st.json({
                            "timestamp": self.message.timestamp.isoformat(),
                            "metadata": self.message.metadata,
                            "message_id": id(self.message)
                        })
                        
        except Exception as e:
            error_context = {
                "message_type": "user",
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern der Benutzernachricht"
            )
            st.error("Fehler beim Anzeigen der Nachricht")
    
    @log_function_call(logger)
    def _render_assistant_message(self) -> None:
        """
        Rendert eine Assistentennachricht.
        
        Stellt die Antwort mit Bot-Avatar, Quellen und optionalen
        Debug-Informationen im ChatGPT-Stil dar.
        """
        try:
            with st.chat_message("assistant", avatar="🤖"):
                # Hauptantwort
                st.markdown(self.message.content)
                
                # Interaktive Quellenangaben
                context_docs = self.message.metadata.get("context_documents", [])
                if context_docs:
                    with st.expander("📚 Verwendete Quellen", expanded=False):
                        for i, doc_id in enumerate(context_docs, 1):
                            st.markdown(
                                f"{i}. Dokument: `{doc_id}`"
                            )
                
                # Zeitstempel und Metriken
                col1, col2 = st.columns([3,1])
                with col1:
                    if context_docs:
                        st.caption(
                            f"🔍 {len(context_docs)} Quellen verwendet"
                        )
                with col2:
                    if st.session_state.get("show_timestamps"):
                        st.caption(
                            f"⏰ {self.message.timestamp.strftime('%H:%M')}"
                        )
                
                # Debug-Informationen
                if st.session_state.get("debug_mode"):
                    with st.expander("🔍 Debug Info"):
                        response_time = self.message.metadata.get(
                            "response_time", "N/A"
                        )
                        st.json({
                            "timestamp": self.message.timestamp.isoformat(),
                            "response_time": response_time,
                            "model": self.message.metadata.get("model"),
                            "context_docs_count": len(context_docs),
                            "message_id": id(self.message)
                        })
            
        except Exception as e:
            error_context = {
                "message_type": "assistant",
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern der Assistentennachricht"
            )
            st.error("Fehler beim Anzeigen der Assistentennachricht")

    @log_function_call(logger)
    def _render_system_message(self) -> None:
        """
        Rendert eine Systemnachricht.
        
        Stellt Systemnachrichten in kursiv und mit speziellem
        Styling im ChatGPT-Stil dar.
        """
        try:
            with st.chat_message("system", avatar="ℹ️"):
                st.markdown(f"*{self.message.content}*")
                
                if st.session_state.get("debug_mode"):
                    with st.expander("🔍 System Info"):
                        st.json({
                            "type": "system_message",
                            "timestamp": self.message.timestamp.isoformat(),
                            "message_id": id(self.message)
                        })
            
        except Exception as e:
            error_context = {
                "message_type": "system",
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern der Systemnachricht"
            )
            st.error("Fehler beim Anzeigen der Systemnachricht")
    
    @log_function_call(logger)
    def render(self) -> None:
        """
        Rendert die Chat-Nachricht.
        
        Wählt basierend auf der Nachrichtenrolle die entsprechende
        Render-Methode und stellt die Nachricht im ChatGPT-Stil dar.
        """
        try:
            # Nachricht basierend auf Rolle rendern
            if self.message.role == "user":
                self._render_user_message()
            elif self.message.role == "assistant":
                self._render_assistant_message()
            elif self.message.role == "system":
                self._render_system_message()
            
            self.logger.debug(
                "Nachricht gerendert",
                extra={
                    "message_role": self.message.role,
                    "message_length": len(self.message.content),
                    "session_id": st.session_state.get("session_id")
                }
            )
            
        except Exception as e:
            error_context = {
                "message_role": self.message.role,
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern der Nachricht"
            )
            st.error(
                "🚫 Die Nachricht konnte nicht angezeigt werden. "
                "Bitte laden Sie die Seite neu."
            )