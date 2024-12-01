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
            layout="centered",  # Geändert zu centered für besseres Chat-Layout
            initial_sidebar_state="expanded",
            menu_items={
                'Get Help': 'mailto:support@example.com',
                'Report a bug': "mailto:bugs@example.com",
                'About': "# Fahrzeugexperten-Chatbot\nIhr persönlicher Assistent für Fahrzeugfragen."
            }
        )
        
        # CSS laden
        self._load_css()
    
    def _load_css(self):
        """Lädt benutzerdefiniertes CSS für die Anwendung."""
        st.markdown("""
            <style>
                /* Verbesserte Chat-Container */
                .stChatMessage {
                    background: rgba(240, 242, 246, 0.4);
                    border: 1px solid rgba(49, 51, 63, 0.1);
                    border-radius: 10px;
                    padding: 1rem;
                    margin-bottom: 1.5rem;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    transition: all 0.2s ease;
                }
                
                /* Avatar Styling */
                .stChatMessage .stAvatar {
                    margin-right: 1rem;
                    border-radius: 10px;
                    padding: 0.2rem;
                    background: white;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }

                /* Nachrichteninhalt */
                .stChatMessage .stMarkdown {
                    padding: 0.5rem 0;
                    line-height: 1.6;
                }
                
                /* Timestamps und Metadaten */
                .stChatMessage .stCaptionContainer {
                    margin-top: 0.5rem;
                    opacity: 0.7;
                    font-size: 0.85rem;
                }

                /* Dark Mode Anpassungen */
                @media (prefers-color-scheme: dark) {
                    .stChatMessage {
                        background: rgba(49, 51, 63, 0.2);
                        border-color: rgba(250, 250, 250, 0.1);
                    }
                    
                    .stChatMessage .stAvatar {
                        background: rgba(49, 51, 63, 0.3);
                    }
                }

                /* Hover-Effekte */
                .stChatMessage:hover {
                    transform: translateY(-1px);
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                }

                /* Layout-Optimierungen */
                .main .chat-messages {
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 2rem 1rem;
                }

                .chat-input {
                    max-width: 800px;
                    margin: 0 auto;
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
                # Services starten
                await self.state_manager.initialize()
                
                # Session-State initialisieren falls nicht vorhanden
                if "chat_initialized" not in st.session_state:
                    st.session_state.chat_initialized = True
                    st.session_state.messages = []
                    st.session_state.is_typing = False
                    st.session_state.last_update = datetime.utcnow()
                
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
        """Rendert die modernisierte Seitenleiste mit Einstellungen und Metriken."""
        with st.sidebar:
            st.markdown("### ⚙️ Chat-Einstellungen")
            
            # Einstellungen in Tabs organisieren
            tab1, tab2 = st.tabs(["🎨 Darstellung", "🛠️ Erweitert"])
            
            with tab1:
                # Theme-Auswahl
                theme = st.selectbox(
                    "Design",
                    ["System", "Hell", "Dunkel"],
                    help="Wählen Sie das Erscheinungsbild der Anwendung"
                )
                
                # Chat-Darstellung
                st.session_state.show_timestamps = st.toggle(
                    "Zeitstempel anzeigen",
                    value=st.session_state.get("show_timestamps", False)
                )
                
                st.session_state.show_sources = st.toggle(
                    "Quellen automatisch ausklappen",
                    value=st.session_state.get("show_sources", False)
                )
            
            with tab2:
                # Debug-Modus
                debug_mode = st.toggle(
                    "Debug-Modus",
                    value=st.session_state.get("debug_mode", False),
                    help="Zeigt technische Details und Entwicklerinformationen"
                )
                
                if debug_mode != st.session_state.get("debug_mode"):
                    self.logger.info(
                        f"Debug-Modus {'aktiviert' if debug_mode else 'deaktiviert'}",
                        extra={"session_id": st.session_state.get("session_id")}
                    )
                    st.session_state.debug_mode = debug_mode
            
            # Chat-Aktionen
            st.markdown("### 🔄 Aktionen")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Chat löschen", use_container_width=True):
                    self.state_manager.clear_chat()
                    self.logger.info(
                        "Chat-Verlauf gelöscht",
                        extra={"session_id": st.session_state.get("session_id")}
                    )
                    st.rerun()
            
            with col2:
                if st.button("📥 Exportieren", use_container_width=True):
                    # TODO: Chat-Export-Funktionalität implementieren
                    pass
            
            # Metriken und Debug-Info
            if debug_mode:
                st.markdown("### 📊 Metriken")
                metrics = self.state_manager.get_metrics()
                
                # Performance-Metriken
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Nachrichten", 
                        metrics['total_messages']
                    )
                with col2:
                    st.metric(
                        "Antwortzeit",
                        f"{metrics.get('last_response_time', 0):.2f}s"
                    )
                
                # Detaillierte Debug-Informationen
                with st.expander("🔍 Debug-Details", expanded=False):
                    st.json({
                        "session": {
                            "id": st.session_state.get('session_id'),
                            "start": metrics.get('session_start'),
                            "duration": f"{metrics.get('session_duration', 0):.1f}s"
                        },
                        "performance": {
                            "cache_hits": f"{metrics.get('cache_hit_rate', 0):.1%}",
                            "errors": metrics['errors_occurred']
                        },
                        "system": {
                            "theme": theme,
                            "timestamps": st.session_state.get('show_timestamps'),
                            "sources": st.session_state.get('show_sources')
                        }
                    })
    
    @log_function_call(logger)
    async def _handle_message(self, message: str) -> None:
        """
        Verarbeitet eine neue Chat-Nachricht und streamt die Antwort.
    
        Zeigt einen Typing-Indikator während der Verarbeitung und
        streamt die Antwort des Assistenten in Echtzeit.
    
        Args:
            message: Benutzernachricht
            
        Raises:
            Exception: Bei Fehlern in der Nachrichtenverarbeitung
        """
        try:
            with st.chat_message("assistant", avatar="🤖"):
                # Platzhalter für die gestreamte Antwort
                message_placeholder = st.empty()
                full_response = ""
            
                # Antwort streamen
                async for chunk in self.state_manager.send_message(message):
                    full_response += chunk + " "
                    # Cursor-Animation während des Streamings
                    message_placeholder.markdown(full_response + "▌")
                    await asyncio.sleep(0.02)  # Natürliche Typing-Geschwindigkeit
            
                # Finale Antwort ohne Cursor anzeigen
                message_placeholder.markdown(full_response)
            
                # Metadaten anzeigen wenn aktiviert
                if st.session_state.get("show_sources", False):
                    self._render_response_metadata(message)

                self.logger.info(
                    "Nachricht erfolgreich verarbeitet",
                    extra={
                        "message_length": len(message),
                        "response_length": len(full_response),
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
                "🚫 Fehler bei der Verarbeitung Ihrer Nachricht. "
                "Bitte versuchen Sie es erneut."
            )
    
    def _render_header(self) -> None:
        """Rendert den modernisierten Anwendungsheader."""
        col1, col2 = st.columns([3,1])
        
        with col1:
            st.title("🚗 Fahrzeugexperten-Chatbot")
            if st.session_state.get("debug_mode"):
                st.caption(f"Session ID: `{st.session_state.get('session_id')}`")
        
        with col2:
            # System-Status
            status_color = "#4CAF50" if not st.session_state.get("is_typing") else "#FFC107"
            status_text = "Bereit" if not st.session_state.get("is_typing") else "Verarbeitet..."
            
            st.markdown(
                f"""
                <div class="status-badge">
                    <span style="background: {status_color}; width: 8px; height: 8px; 
                               border-radius: 50%; margin-right: 6px;"></span>
                    {status_text}
                </div>
                """,
                unsafe_allow_html=True
            )
    
    def _render_response_metadata(self, response: Message) -> None:
        """
        Rendert erweiterte Metadaten für eine Assistentenantwort.
        
        Args:
            response: Antwortnachricht mit Metadaten
        """
        context_docs = response.metadata.get("context_documents", [])
        
        if context_docs:
            with st.expander(
                f"📚 {len(context_docs)} Quellen verwendet",
                expanded=st.session_state.get("show_sources", False)
            ):
                for i, doc_id in enumerate(context_docs, 1):
                    st.markdown(f"{i}. `{doc_id}`")
        
        if st.session_state.get("debug_mode"):
            with st.expander("🔍 Response Details", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        "Verarbeitungszeit",
                        f"{response.metadata.get('response_time', 'N/A')}s"
                    )
                with col2:
                    st.metric(
                        "Token",
                        len(response.content.split())
                    )
                
                st.json({
                    "model": response.metadata.get("model", "N/A"),
                    "context_docs_used": len(context_docs),
                    "timestamp": response.timestamp.isoformat()
                })
    
    def _enable_auto_scroll(self) -> None:
        """Aktiviert automatisches Scrollen zum Ende des Chats mit verbesserter Zuverlässigkeit."""
        st.markdown("""
            <script>
                function scrollToBottom() {
                    // Warte kurz bis der DOM vollständig aktualisiert ist
                    setTimeout(() => {
                        const messages = document.querySelector('[data-testid="stVerticalBlock"]');
                        if (messages) {
                            messages.scrollTo({
                                top: messages.scrollHeight,
                                behavior: 'smooth'
                            });
                        }
                    }, 100);
                }
                
                // Event-Listener für neue Nachrichten
                const observer = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        if (mutation.addedNodes.length) {
                            scrollToBottom();
                        }
                    });
                });

                // Beobachtung starten wenn DOM geladen ist
                document.addEventListener('DOMContentLoaded', () => {
                    const messages = document.querySelector('[data-testid="stVerticalBlock"]');
                    if (messages) {
                        observer.observe(messages, { 
                            childList: true, 
                            subtree: true,
                            characterData: true
                        });
                        scrollToBottom();
                    }
                });

                // Initiales Scrollen
                scrollToBottom();
            </script>
        """, unsafe_allow_html=True)

    @log_function_call(logger)
    async def render(self) -> None:
        """
        Rendert die komplette Anwendung mit korrektem Layout.
        
        Features:
        - Chat-Input immer sichtbar am unteren Bildschirmrand
        - Chat-Nachrichten nur oberhalb des Inputs
        - Automatisches Scrollen zu neuen Nachrichten
        """
        try:
            with log_execution_time(self.logger, "app_rendering"):
                # Initialisierung prüfen
                if not await self.initialize():
                    st.error(
                        "🚫 Die Anwendung konnte nicht initialisiert werden. "
                        "Bitte laden Sie die Seite neu."
                    )
                    return
                
                # Header und Sidebar rendern
                self._render_header()
                self._render_sidebar()
                
                # CSS für optimiertes Layout
                st.markdown("""
                    <style>
                        /* Anpassung der Hauptcontainer-Höhe und Scrollbereich */
                        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
                            height: calc(100vh - 180px);
                            overflow-y: auto;
                            padding-bottom: 80px;  /* Reduziert von 100px */
                        }
                        
                        /* Chat-Input fixiert am unteren Rand */
                        .stChatInputContainer {
                            position: fixed;
                            bottom: 0;
                            left: 0;
                            right: 0;
                            padding: 0.5rem 2rem;  /* Reduziert von 1rem */
                            background: var(--background-color);
                            border-top: 1px solid rgba(49, 51, 63, 0.2);
                            backdrop-filter: blur(10px);
                            z-index: 100;
                            margin-bottom: 0 !important;  /* Entfernt zusätzlichen Abstand unten */
                        }
                        
                        /* Streamlit Container-Anpassungen */
                        .stChatMessage {
                            margin-bottom: 0.5rem !important;  /* Reduziert von 1rem */
                        }
                        
                        /* Reduziert den Abstand nach Chat-Nachrichten */
                        .stChatMessage .element-container {
                            margin-bottom: 0.25rem !important;
                        }
                        
                        /* Entfernt überschüssigen Abstand nach Checkboxen */
                        .stChatMessage [data-testid="stVerticalBlock"] {
                            gap: 0.25rem !important;
                        }
                        
                        /* Stelle sicher, dass neue Nachrichten immer sichtbar sind */
                        .element-container:last-child {
                            margin-bottom: 80px;  /* Reduziert von 100px */
                        }
                        /* Chat-Input fixiert am unteren Rand */
                        .stChatInputContainer {
                            position: fixed;
                            bottom: 0;
                            left: 0;
                            right: 0;
                            padding: 0.5rem 2rem;
                            background: var(--background-color);
                            border-top: 1px solid rgba(49, 51, 63, 0.2);
                            backdrop-filter: blur(10px);
                            z-index: 100;
                            margin: 0 !important;  /* Entfernt ALLE Margins */
                        }
                        
                        /* Entfernt zusätzliche Container-Margins */
                        .stChatInputContainer > div {
                            margin: 0 !important;
                        }
                        
                        /* Entfernt den Standard-Streamlit-Abstand am Ende */
                        footer {
                            display: none !important;
                        }
                        
                        /* Anpasst den Hauptcontainer-Abstand */
                        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
                            padding-bottom: 60px;  /* Reduziert von 80px */
                        }
                    </style>
""", unsafe_allow_html=True)
                
                # Fehler anzeigen falls vorhanden
                if self.state_manager.has_error():
                    st.error(self.state_manager.get_error())
                    self.state_manager.clear_error()
                
                # Chat-Verlauf anzeigen
                messages = self.state_manager.get_messages()
                for message in messages:
                    ChatMessage(message).render()
                
                # Chat Input
                if prompt := st.chat_input(
                    "Stellen Sie Ihre Frage...",
                    key="chat_input",
                    disabled=st.session_state.get("is_typing", False)
                ):
                    # Benutzernachricht anzeigen
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(prompt)
                        if st.session_state.get("show_timestamps"):
                            st.caption(f"⏰ {datetime.now().strftime('%H:%M')}")
                    
                    # Antwort generieren und streamen
                    await self._handle_message(prompt)
                
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