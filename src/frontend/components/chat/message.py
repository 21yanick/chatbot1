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
    kontextabhängige Darstellungsoptionen.
    """
    
    def __init__(self, message: Message):
        """
        Initialisiert die Nachrichtenkomponente.
        
        Args:
            message: Darzustellende Nachricht
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.message = message

    def _get_message_style(self) -> Dict[str, str]:
        """
        Ermittelt das Styling für den Nachrichtentyp.
        
        Returns:
            Dict mit CSS-Styles für den Container
        """
        base_style = {
            "padding": "1rem",
            "border-radius": "0.5rem",
            "margin-bottom": "1rem",
        }
        
        if self.message.role == "user":
            base_style.update({
                "background-color": "#f0f2f6",
                "border-left": "4px solid #6c757d"
            })
        elif self.message.role == "assistant":
            base_style.update({
                "background-color": "#e8f0fe",
                "border-left": "4px solid #1e88e5"
            })
        elif self.message.role == "system":
            base_style.update({
                "background-color": "#fff3e0",
                "border-left": "4px solid #ffa726"
            })
            
        return base_style
    
    def _style_to_string(self, style_dict: Dict[str, str]) -> str:
        """
        Konvertiert Style-Dict in CSS-String.
        
        Args:
            style_dict: Dictionary mit CSS-Eigenschaften
            
        Returns:
            Formatierter CSS-String
        """
        return "; ".join(f"{k}: {v}" for k, v in style_dict.items())
    
    @log_function_call(logger)
    def _render_user_message(self) -> None:
        """
        Rendert eine Benutzernachricht.
        
        Stellt die Nachricht mit Benutzer-Icon und entsprechendem
        Styling dar.
        """
        try:
            with st.container():
                col1, col2 = st.columns([1, 11])
                with col1:
                    st.markdown("👤")
                with col2:
                    st.markdown(self.message.content)
                    
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
    def _render_system_message(self) -> None:
        """
        Rendert eine Systemnachricht.
        
        Stellt Systemnachrichten in kursiv und mit speziellem
        Styling dar.
        """
        try:
            with st.container():
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
    def _render_assistant_message(self) -> None:
        """
        Rendert eine Assistentennachricht.
        
        Stellt die Antwort mit Bot-Icon, Quellen und optionalen
        Debug-Informationen dar.
        """
        try:
            with st.container():
                col1, col2 = st.columns([1, 11])
                with col1:
                    st.markdown("🤖")
                with col2:
                    # Hauptantwort
                    st.markdown(self.message.content)
                    
                    # Quellen anzeigen
                    context_docs = self.message.metadata.get("context_documents", [])
                    if context_docs:
                        with st.expander("📚 Verwendete Quellen"):
                            for i, doc_id in enumerate(context_docs, 1):
                                st.markdown(
                                    f"{i}. Dokument: `{doc_id}`"
                                )
                    
                    # Performance-Metriken
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

    def _render_timestamp(self) -> None:
        """Rendert den Zeitstempel der Nachricht wenn aktiviert."""
        if st.session_state.get("show_timestamps"):
            timestamp_str = self.message.timestamp.strftime("%H:%M:%S")
            st.caption(f"⏰ {timestamp_str}")
    
    @log_function_call(logger)
    def render(self) -> None:
        """
        Rendert die Chat-Nachricht.
        
        Wählt basierend auf der Nachrichtenrolle die entsprechende
        Render-Methode und fügt Container-Styling und Zeitstempel hinzu.
        """
        try:
            with log_execution_time(self.logger, "message_rendering"):
                with st.container():
                    # Styles anwenden
                    style = self._get_message_style()
                    st.markdown(
                        f'<div style="{self._style_to_string(style)}">',
                        unsafe_allow_html=True
                    )
                    
                    # Nachricht basierend auf Rolle rendern
                    if self.message.role == "user":
                        self._render_user_message()
                    elif self.message.role == "assistant":
                        self._render_assistant_message()
                    elif self.message.role == "system":
                        self._render_system_message()
                    
                    # Container schließen
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Zeitstempel anzeigen
                    self._render_timestamp()
            
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