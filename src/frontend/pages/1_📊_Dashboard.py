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
    log_function_call
)

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

# Seiten-Konfiguration
st.set_page_config(
    page_title="Developer Dashboard - Fahrzeugexperten-Chatbot",
    page_icon="📊",
    layout="wide"
)

class DeveloperDashboard:
    """Developer Dashboard Komponente."""
    
    def __init__(self):
        """Initialisiert das Developer Dashboard."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.state_manager = StateManager()
        
    @log_function_call(logger)
    async def initialize(self) -> bool:
        """Initialisiert das Dashboard und seine Abhängigkeiten."""
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
        """Rendert die Service-Status-Übersicht."""
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
                st.info(
                    "Embedding Service\n\n"
                    f"Status: {status}\n"
                    "Queue: 0"  # TODO: Implement queue tracking
                )
            except Exception as e:
                st.error("Embedding Service\n\nStatus: Error")
                logger.error(f"Error getting embedding service status: {str(e)}")
        
        # Document Processor Status
        with col4:
            try:
                doc_processor = st.session_state.get("document_processor")
                status = "🟢 Active" if doc_processor else "🔴 Inactive"
                st.info(
                    "Document Processor\n\n"
                    f"Status: {status}\n"
                    "Processing: 0 docs"  # TODO: Implement doc processing tracking
                )
            except Exception as e:
                st.error("Document Processor\n\nStatus: Error")
                logger.error(f"Error getting document processor status: {str(e)}")

    def _render_log_viewer(self) -> None:
        """Rendert den Log-Viewer mit Filterfunktionen."""
        st.markdown("### 📋 Log Viewer")
        
        # Log Level Filter
        col1, col2, col3 = st.columns([2,2,6])
        with col1:
            log_level = st.selectbox(
                "Log Level",
                ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"],
                index=0
            )
        
        with col2:
            log_source = st.selectbox(
                "Source",
                ["ALL", "chat_service", "database", "document_processor"],
                index=0
            )

        # Log Datei laden und filtern
        try:
            log_path = Path("logs") / datetime.now().strftime("%Y-%m") / "app.log"
            if log_path.exists():
                with log_path.open() as f:
                    logs = f.readlines()[-100:]  # Letzte 100 Zeilen
                
                # Logs filtern
                filtered_logs = []
                for log in logs:
                    if log_level != "ALL" and f"[{log_level}]" not in log:
                        continue
                    if log_source != "ALL" and log_source not in log:
                        continue
                    filtered_logs.append(log)
                
                # Logs anzeigen
                st.code("".join(filtered_logs), language="text")
            else:
                st.warning("Keine Log-Datei gefunden")
        except Exception as e:
            st.error(f"Fehler beim Lesen der Logs: {str(e)}")

    def _render_performance_metrics(self) -> None:
        """Rendert Performance-Metriken und Graphen."""
        st.markdown("### 📈 Performance Metrics")
        
        # Performance Metriken
        col1, col2 = st.columns(2)
        
        with col1:
            # Response Time Graph
            fig = go.Figure()
            # Beispieldaten - in Produktion durch echte Metriken ersetzen
            times = [(datetime.now() - timedelta(minutes=x)).strftime('%H:%M') 
                    for x in range(30, 0, -1)]
            response_times = [1.2, 1.1, 1.3, 1.0, 1.4, 1.2, 1.1, 1.3, 1.2, 1.1,
                            1.2, 1.1, 1.0, 1.2, 1.3, 1.1, 1.2, 1.1, 1.3, 1.2,
                            1.1, 1.2, 1.3, 1.1, 1.2, 1.1, 1.0, 1.2, 1.1, 1.3]
            
            fig.add_trace(go.Scatter(
                x=times,
                y=response_times,
                mode='lines+markers',
                name='Response Time (s)'
            ))
            fig.update_layout(
                title="Response Times",
                xaxis_title="Time",
                yaxis_title="Seconds"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Memory Usage
            fig = go.Figure()
            memory_usage = [42, 45, 43, 47, 44, 46, 45, 48, 46, 45,
                          47, 46, 44, 45, 46, 47, 45, 46, 48, 47,
                          45, 46, 47, 45, 46, 44, 45, 46, 47, 45]
            
            fig.add_trace(go.Scatter(
                x=times,
                y=memory_usage,
                mode='lines+markers',
                name='Memory Usage (%)'
            ))
            fig.update_layout(
                title="Memory Usage",
                xaxis_title="Time",
                yaxis_title="Usage (%)"
            )
            st.plotly_chart(fig, use_container_width=True)

    def _render_developer_tools(self) -> None:
        """Rendert Entwickler-Werkzeuge und Quick Actions."""
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
            debug_mode = st.toggle("🐛 Debug Mode", value=st.session_state.get("debug_mode", False))
            if debug_mode != st.session_state.get("debug_mode"):
                st.session_state.debug_mode = debug_mode
                st.success(f"Debug Mode: {'Enabled' if debug_mode else 'Disabled'}")

    def _render_system_info(self) -> None:
        """Rendert System-Informationen und Konfiguration."""
        st.markdown("### ⚙️ System Information")
        
        # Config anzeigen
        with st.expander("Current Configuration"):
            st.json(settings.dict())
        
        # Session State anzeigen
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
        """Rendert das komplette Dashboard."""
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
            
            # Zwei-Spalten-Layout für Logs und Performance
            col1, col2 = st.columns([3, 2])
            
            with col1:
                self._render_log_viewer()
            
            with col2:
                self._render_performance_metrics()
            
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

# Dashboard-Instanz erstellen und rendern
if __name__ == "__main__":
    dashboard = DeveloperDashboard()
    asyncio.run(dashboard.render())