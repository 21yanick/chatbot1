"""
Developer Dashboard - Entwickler-Übersichtsseite

Bietet Monitoring und Debug-Funktionen für:
- Service Status und Performance
- Log Monitoring 
- System Metriken
- Entwickler Tools
"""

import streamlit as st
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import plotly.graph_objects as go
from typing import Dict, List, Any, Optional
import plotly.express as px

from src.frontend.utils.state_manager import StateManager
from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call,
    setup_logging
)

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

# Seiten-Konfiguration
st.set_page_config(
    page_title="Developer Dashboard - Fahrzeugexperten-Chatbot",
    page_icon="📊",
    layout="wide"
)

# Logging Setup initialisieren
setup_logging(
    debug=st.session_state.get("debug_mode", False),
    log_dir="logs",
    enable_performance_logging=True
)

class DeveloperDashboard:
    """Developer Dashboard Komponente."""
    
    def __init__(self):
        """Initialisiert das Developer Dashboard."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.state_manager = StateManager()
        
    @log_function_call(logger)
    async def initialize(self) -> bool:
        """
        Initialisiert das Dashboard und seine Abhängigkeiten.
        
        Returns:
            bool: True wenn die Initialisierung erfolgreich war, sonst False
        """
        try:
            with log_execution_time(self.logger, "dashboard_initialization"):
                await self.state_manager.initialize()
                return True
        except Exception as e:
            log_error_with_context(
                self.logger,
                e,
                {"session_id": st.session_state.get("session_id")},
                "Fehler bei Dashboard-Initialisierung"
            )
            return False

    def _render_service_status(self) -> None:
        """
        Rendert die Service-Status-Übersicht.
        Zeigt den aktuellen Status aller Services in einer übersichtlichen Grid-Ansicht.
        """
        st.markdown("### 🔌 Service Status")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Chat Service Status
        with col1:
            try:
                chat_service = st.session_state.get("chat_service")
                model_name = chat_service._llm.model_name if chat_service else "Not initialized"
                temperature = chat_service.temperature if chat_service else "N/A"
                st.info(
                    "Chat Service\n\n"
                    f"Model: {model_name}\n"
                    f"Temperature: {temperature}"
                )
            except Exception as e:
                st.error("Chat Service\n\nStatus: Error")
                logger.error(f"Error getting chat service status: {str(e)}")
        
        # ChromaDB Status
        with col2:
            try:
                retrieval_service = st.session_state.get("retrieval_service")
                chroma_status = "🟢 Connected" if (
                    retrieval_service and 
                    retrieval_service._db_manager._collection is not None
                ) else "🔴 Disconnected"
                collection_name = settings.database.collection_name
                st.info(
                    "ChromaDB\n\n"
                    f"Status: {chroma_status}\n"
                    f"Collection: {collection_name}"
                )
            except Exception as e:
                st.error("ChromaDB\n\nStatus: Error")
                logger.error(f"Error getting ChromaDB status: {str(e)}")
        
        # Embedding Service Status
        with col3:
            try:
                embedding_service = st.session_state.get("embedding_service")
                status = "🟢 Active" if embedding_service else "🔴 Inactive"
                queue_size = 0  # TODO: Implement queue tracking
                st.info(
                    "Embedding Service\n\n"
                    f"Status: {status}\n"
                    f"Queue: {queue_size}"
                )
            except Exception as e:
                st.error("Embedding Service\n\nStatus: Error")
                logger.error(f"Error getting embedding service status: {str(e)}")
        
        # Document Processor Status
        with col4:
            try:
                doc_processor = st.session_state.get("document_processor")
                status = "🟢 Active" if doc_processor else "🔴 Inactive"
                processing_count = 0  # TODO: Implement doc processing tracking
                st.info(
                    "Document Processor\n\n"
                    f"Status: {status}\n"
                    f"Processing: {processing_count} docs"
                )
            except Exception as e:
                st.error("Document Processor\n\nStatus: Error")
                logger.error(f"Error getting document processor status: {str(e)}")

    def _render_log_viewer(self) -> None:
        """
        Rendert den Log-Viewer mit erweiterten Filterfunktionen.
        
        Features:
        - Filterung nach Log-Level und Service
        - Automatische Aktualisierung
        - Debug-Informationen im Debug-Mode
        - Fehlerbehandlung mit benutzerfreundlichen Meldungen
        """
        st.markdown("### 📋 Log Viewer")
        
        # Log Level und Source Filter in Columns
        col1, col2, col3 = st.columns([2,2,6])
        
        with col1:
            log_level = st.selectbox(
                "Log Level",
                ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                index=0,
                help="Filtere Logs nach ihrer Wichtigkeit"
            )
        
        with col2:
            log_source = st.selectbox(
                "Source",
                ["ALL", "chat_service", "database", "document_processor"],
                index=0,
                help="Filtere Logs nach ihrer Quelle"
            )
            
        with col3:
            auto_refresh = st.toggle(
                "Auto-Refresh",
                value=False,
                help="Aktualisiert die Logs automatisch alle 30 Sekunden"
            )

        # Log Datei laden und filtern
        try:
            # Korrekten Log-Pfad für aktuelles Monat erstellen
            current_month_dir = datetime.now().strftime("%Y-%m")
            log_path = Path("logs") / current_month_dir / "app.log"
            
            if log_path.exists():
                with log_path.open(encoding='utf-8') as f:
                    # Lese die letzten 100 Zeilen
                    # TODO: Mach dies konfigurierbar über ein Slider-Widget
                    logs = f.readlines()[-100:]
                
                # Logs filtern basierend auf Benutzerauswahl
                filtered_logs = []
                for log in logs:
                    try:
                        # Prüfe Log-Level Filter
                        if log_level != "ALL" and f"[{log_level}]" not in log:
                            continue
                            
                        # Prüfe Source Filter
                        if log_source != "ALL" and log_source not in log:
                            continue
                            
                        filtered_logs.append(log)
                    except Exception as e:
                        self.logger.error(f"Fehler beim Filtern des Logs: {str(e)}")
                
                # Logs anzeigen
                if filtered_logs:
                    log_container = st.container()
                    with log_container:
                        st.code("".join(filtered_logs), language="text")
                        
                    # Auto-Refresh wenn aktiviert
                    if auto_refresh:
                        st.rerun()
                else:
                    st.info("Keine Logs für die gewählten Filter gefunden")
            else:
                st.info(f"Keine Log-Datei gefunden unter: {log_path}")
                
                # Debug-Informationen anzeigen wenn Debug-Mode aktiv
                if st.session_state.get("debug_mode"):
                    with st.expander("Debug Info"):
                        st.markdown(f"""
                        **Log File Details:**
                        - Gesuchter Pfad: `{log_path}`
                        - Existiert logs/: `{Path("logs").exists()}`
                        - Existiert logs/{current_month_dir}/: `{(Path("logs") / current_month_dir).exists()}`
                        """)
        except Exception as e:
            st.error("🚫 Fehler beim Lesen der Logs")
            if st.session_state.get("debug_mode"):
                st.exception(e)
            log_error_with_context(
                self.logger,
                e,
                {
                    "log_path": str(log_path),
                    "log_level": log_level,
                    "log_source": log_source
                },
                "Fehler beim Laden der Logs"
            )

    

    def _render_developer_tools(self) -> None:
        """
        Rendert Entwickler-Werkzeuge und Quick Actions.
        Bietet schnellen Zugriff auf wichtige Entwicklerfunktionen.
        """
        st.markdown("### 🛠️ Developer Tools")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📥 Clear Cache", use_container_width=True):
                st.session_state.clear()
                st.success("Cache cleared!")
        
        with col2:
            if st.button("🗑️ Reset ChromaDB", use_container_width=True):
                # TODO: Implementiere ChromaDB Reset
                st.success("ChromaDB reset initiated!")
        
        with col3:
            if st.button("🔄 Reload Config", use_container_width=True):
                # TODO: Implementiere Config Reload
                st.success("Config reloaded!")
        
        with col4:
            debug_mode = st.toggle(
                "🐛 Debug Mode",
                value=st.session_state.get("debug_mode", False),
                help="Aktiviert erweiterte Debugging-Funktionen"
            )
            if debug_mode != st.session_state.get("debug_mode"):
                st.session_state.debug_mode = debug_mode
                st.success(f"Debug Mode: {'Enabled' if debug_mode else 'Disabled'}")

    def _render_system_info(self) -> None:
        """
        Rendert System-Informationen und Konfiguration.
        Zeigt detaillierte Informationen über das System und den aktuellen Zustand.
        """
        st.markdown("### ⚙️ System Information")
        
        # Config anzeigen
        with st.expander("Current Configuration"):
            st.json(settings.dict())
        
        # Session State anzeigen (gefiltert)
        with st.expander("Session State"):
            # Sensitive Daten filtern
            safe_state = {
                k: v for k, v in st.session_state.items()
                if not isinstance(v, (bytes, type(lambda: None)))
                and str(k) not in ['_client', '_collection', 'password', 'token']
            }
            st.json(safe_state)

    @log_function_call(logger)
    async def render(self) -> None:
        """
        Rendert das komplette Dashboard.
        Koordiniert das Rendering aller Dashboard-Komponenten und behandelt Fehler.
        """
        try:
            # Services initialisieren
            if not await self.initialize():
                st.error("🚫 Dashboard konnte nicht initialisiert werden")
                return
            
            # Dashboard Header
            st.title("📊 Developer Dashboard")
            st.markdown("Entwickler-Übersicht und Debugging-Tools")
            
            # Dashboard Komponenten
            self._render_service_status()
            st.divider()
            
            # Log Viewer in voller Breite
            self._render_log_viewer()
            st.divider()
            
            self._render_developer_tools()
            st.divider()
            
            self._render_system_info()
            
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern des Dashboards"
            )
            st.error(
                "🚫 Fehler beim Laden des Dashboards. "
                "Bitte versuchen Sie es später erneut."
            )
            
            # Im Debug-Mode zusätzliche Fehlerinformationen anzeigen
            if st.session_state.get("debug_mode"):
                st.exception(e)


# Dashboard-Instanz erstellen und rendern wenn Skript direkt ausgeführt wird
if __name__ == "__main__":
    dashboard = DeveloperDashboard()
    asyncio.run(dashboard.render())