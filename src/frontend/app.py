"""
Hauptanwendungsmodul - Streamlit-basierte UI für den Fahrzeugexperten-Chatbot

Diese Modul implementiert die zentrale Benutzeroberfläche und Chat-Funktionalität.
Es koordiniert:
- UI-Rendering und Layout
- Service-Initialisierung
- Benutzerinteraktionen
- Chat-Logik und Nachrichtenverarbeitung
- Fehlerbehandlung und Statusanzeigen
"""

import streamlit as st
import asyncio
from typing import Optional
from datetime import datetime

from src.frontend.components.chat.message import ChatMessage
from src.frontend.components.chat.input import ChatInput
from src.frontend.utils.state_manager import StateManager
from src.backend.models.chat import Message
from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

# Logger für die Hauptanwendung initialisieren
logger = get_logger(__name__)

class ChatApplication:
    """
    Hauptanwendungsklasse für den Fahrzeugexperten-Chatbot.
    
    Verwaltet den gesamten Anwendungszustand und koordiniert die
    Interaktionen zwischen UI, Services und Benutzern.
    """
    
    def __init__(self):
        """Initialisiert die Hauptanwendung."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.state_manager = StateManager()
        
        # Seiten-Konfiguration
        st.set_page_config(
            page_title="Fahrzeugexperten-Chatbot",
            page_icon="🚗",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # CSS laden
        self._load_css()
    
    def _load_css(self):
        """Lädt benutzerdefiniertes CSS für die Anwendung."""
        st.markdown("""
        <style>
            /* Hauptcontainer-Styling */
            .stApp {
                max-width: 1200px;
                margin: 0 auto;
            }
            
            /* Eingabefeld-Styling */
            .stTextArea {
                font-size: 1rem;
            }
            
            /* Text-Styling */
            .stMarkdown {
                font-size: 1rem;
            }
            
            /* Chat-Container-Styling */
            .chat-container {
                background-color: #f7f7f7;
                border-radius: 10px;
                padding: 20px;
                margin: 10px 0;
            }
            
            /* Debug-Info-Styling */
            .debug-info {
                font-family: monospace;
                font-size: 0.8rem;
                color: #666;
            }
            
            /* Nachricht-Container */
            .message-container {
                margin-bottom: 1rem;
                padding: 0.5rem;
                border-radius: 0.5rem;
            }
            
            /* Status-Anzeigen */
            .status-indicator {
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-right: 5px;
            }
        </style>
        """, unsafe_allow_html=True)
    
    @log_function_call(logger)
    async def initialize(self) -> bool:
        """
        Initialisiert die Anwendung und ihre Services.
        
        Returns:
            bool: True wenn erfolgreich initialisiert
        """
        try:
            with log_execution_time(self.logger, "app_initialization"):
                await self.state_manager.initialize()
                
                self.logger.info(
                    "Anwendung erfolgreich initialisiert",
                    extra={"session_id": st.session_state.get("session_id")}
                )
                return True
                
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Anwendungsinitialisierung"
            )
            return False
    
    def _render_sidebar(self) -> None:
        """Rendert die Seitenleiste mit Einstellungen und Debug-Informationen."""
        with st.sidebar:
            st.markdown("### ⚙️ Einstellungen")
            
            # Debug-Modus
            debug_mode = st.checkbox(
                "🔍 Debug-Modus",
                value=st.session_state.get("debug_mode", False),
                help="Zeigt zusätzliche Debug-Informationen an"
            )
            
            if debug_mode != st.session_state.get("debug_mode"):
                self.logger.info(
                    f"Debug-Modus {'aktiviert' if debug_mode else 'deaktiviert'}",
                    extra={"session_id": st.session_state.get("session_id")}
                )
                st.session_state.debug_mode = debug_mode
            
            # Zeitstempel
            st.session_state.show_timestamps = st.checkbox(
                "⏰ Zeitstempel anzeigen",
                value=st.session_state.get("show_timestamps", False),
                help="Zeigt Zeitstempel für Nachrichten an"
            )
            
            # Theme-Auswahl (optional)
            theme = st.selectbox(
                "🎨 Theme",
                ["Hell", "Dunkel", "System"],
                index=0
            )
            
            # Chat löschen
            if st.button("🗑️ Chat löschen", use_container_width=True):
                self.state_manager.clear_chat()
                self.logger.info(
                    "Chat-Verlauf gelöscht",
                    extra={"session_id": st.session_state.get("session_id")}
                )
                st.rerun()
            
            # Debug-Informationen
            if debug_mode:
                st.markdown("### 🔍 Debug-Informationen")
                metrics = self.state_manager.get_metrics()
                
                st.markdown(
                    f"""
                    <div class="debug-info">
                    <h4>Session-Info</h4>
                    • ID: {st.session_state.get('session_id')}<br>
                    • Start: {metrics.get('session_start', 'N/A')}<br>
                    • Dauer: {metrics.get('session_duration', 0):.1f}s<br>
                    
                    <h4>Metriken</h4>
                    • Nachrichten: {metrics['total_messages']}<br>
                    • Fehler: {metrics['errors_occurred']}<br>
                    • Letzte Antwortzeit: {metrics.get('last_response_time', 'N/A')}s<br>
                    • Cache-Trefferrate: {metrics.get('cache_hit_rate', 0):.1%}<br>
                    
                    <h4>System</h4>
                    • Theme: {theme}<br>
                    • Debug: {'Aktiv' if debug_mode else 'Inaktiv'}<br>
                    • Timestamps: {'An' if st.session_state.get('show_timestamps') else 'Aus'}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
    
    def _render_header(self) -> None:
        """Rendert den Anwendungsheader."""
        st.title("🚗 Fahrzeugexperten-Chatbot")
        
        # Status und Session-Info
        if st.session_state.get("debug_mode"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(
                    f"<small>Session ID: `{st.session_state.get('session_id')}`</small>",
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    '<div class="status-indicator" '
                    'style="background-color: #4CAF50;"></div>'
                    'System aktiv',
                    unsafe_allow_html=True
                )
    
    @log_function_call(logger)
    def _render_chat_history(self) -> None:
        """Rendert den Chat-Verlauf."""
        try:
            with log_execution_time(self.logger, "history_rendering"):
                messages = self.state_manager.get_messages()
                
                for message in messages:
                    ChatMessage(message).render()
                
                self.logger.debug(
                    "Chat-Verlauf gerendert",
                    extra={
                        "message_count": len(messages),
                        "session_id": st.session_state.get("session_id")
                    }
                )
                
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern des Chat-Verlaufs"
            )
            st.error(
                "🚫 Der Chat-Verlauf konnte nicht geladen werden. "
                "Bitte laden Sie die Seite neu."
            )
    
    @log_function_call(logger)
    async def _handle_message(self, message: str) -> Optional[Message]:
        """
        Verarbeitet eine neue Chat-Nachricht.
        
        Args:
            message: Nachrichteninhalt
            
        Returns:
            Optional[Message]: Antwort des Assistenten oder None bei Fehler
        """
        try:
            with request_context():
                with st.spinner("💭 Verarbeite Anfrage..."):
                    response = await self.state_manager.send_message(message)
                    if response:
                        self.logger.info(
                            "Nachricht erfolgreich verarbeitet",
                            extra={
                                "message_length": len(message),
                                "response_length": len(response.content),
                                "session_id": st.session_state.get("session_id")
                            }
                        )
                        ChatMessage(response).render()
                        return response
                    
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
                "🚫 Fehler bei der Verarbeitung Ihrer Nachricht. "
                "Bitte versuchen Sie es erneut."
            )
            return None
    
    def _enable_auto_scroll(self) -> None:
        """Aktiviert automatisches Scrollen zum Ende des Chats."""
        if st.session_state.get("chat_history"):
            st.markdown(
                """
                <script>
                    var chatContainer = window.parent.document.querySelector(
                        '[data-testid="stVerticalBlock"]'
                    );
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                </script>
                """,
                unsafe_allow_html=True
            )
    
    @log_function_call(logger)
    async def render(self) -> None:
        """
        Rendert die komplette Anwendung.
        
        Koordiniert das Rendering aller Komponenten und verwaltet
        den Anwendungszustand.
        """
        try:
            with log_execution_time(self.logger, "app_rendering"):
                # Services initialisieren
                if not await self.initialize():
                    st.error(
                        "🚫 Die Anwendung konnte nicht initialisiert werden. "
                        "Bitte laden Sie die Seite neu."
                    )
                    return
                
                # Layout erstellen
                self._render_header()
                self._render_sidebar()
                
                # Chat-Container
                chat_container = st.container()
                
                with chat_container:
                    # Fehler anzeigen falls vorhanden
                    if self.state_manager.has_error():
                        st.error(self.state_manager.get_error())
                        self.state_manager.clear_error()
                    
                    # Chat-Verlauf anzeigen
                    self._render_chat_history()
                    
                    # Eingabekomponente
                    input_component = ChatInput(
                        on_submit=self._handle_message,
                        placeholder="Stellen Sie Ihre Frage..."
                    )
                    await input_component.render()
                
                # Auto-Scroll aktivieren
                self._enable_auto_scroll()
                
                self.logger.info(
                    "Anwendung erfolgreich gerendert",
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
                "Kritischer Anwendungsfehler"
            )
            st.error(
                "🚫 Ein unerwarteter Fehler ist aufgetreten. "
                "Bitte laden Sie die Seite neu."
            )

# Hauptausführung
if __name__ == "__main__":
    app = ChatApplication()
    with request_context():
        asyncio.run(app.render())