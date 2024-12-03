"""
Developer Dashboard - Advanced Monitoring und Debug Interface

Bietet ein erweitertes Dashboard für:
- Service Monitoring und Management
- Datenbank-Insights
- Performance Tracking
- System Debug Tools
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio

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

logger = get_logger(__name__)

class ServiceMetrics:
    """Verwaltet Service-bezogene Metriken."""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def get_chat_metrics(self) -> Dict[str, Any]:
        """Sammelt Chat-Service Metriken."""
        try:
            chat_service = st.session_state.get("chat_service")
            if not chat_service:
                return {"status": "Not Initialized"}
            
            return {
                "status": "Active",
                "model": chat_service.model_name,
                "temperature": chat_service.temperature,
                "max_tokens": chat_service.max_tokens,
                "active_sessions": len(chat_service._sessions),
                "messages_processed": st.session_state.metrics.get("messages_sent", 0),
                "avg_response_time": st.session_state.metrics.get("last_response_time", 0)
            }
        except Exception as e:
            self.logger.error(f"Error getting chat metrics: {str(e)}")
            return {"status": "Error", "error": str(e)}

    def get_db_metrics(self) -> Dict[str, Any]:
        """Sammelt Datenbank-Metriken."""
        try:
            retrieval_service = st.session_state.get("retrieval_service")
            if not retrieval_service:
                return {"status": "Not Connected"}
            
            # Direkt auf die Collection zugreifen
            if not hasattr(retrieval_service.db, "collection"):
                return {"status": "Not Connected"}
            
            collection = retrieval_service.db.collection
            return {
                "status": "Connected",
                "collection": settings.database.collection_name,
                "document_count": collection.count(),
                "persist_directory": settings.database.persist_directory
            }
        except Exception as e:
            self.logger.error(f"Error getting DB metrics: {str(e)}")
            return {"status": "Error", "error": str(e)}

class DashboardTabs:
    """Verwaltet die verschiedenen Dashboard-Tabs."""
    
    def __init__(self):
        self.metrics = ServiceMetrics(StateManager())
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def render_overview_tab(self):
        """Rendert den Overview Tab mit den wichtigsten Metriken."""
        st.header("📊 System Overview")
        
        # Service Status Cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            chat_metrics = self.metrics.get_chat_metrics()
            st.info("💬 Chat Service", icon="💬")
            st.metric("Status", chat_metrics["status"])
            if chat_metrics["status"] == "Active":
                st.metric("Messages Processed", chat_metrics["messages_processed"])
                st.metric("Active Sessions", chat_metrics["active_sessions"])

        with col2:
            db_metrics = self.metrics.get_db_metrics()
            st.info("🗄 Database", icon="🗄")
            st.metric("Status", db_metrics["status"])
            if db_metrics["status"] == "Connected":
                st.metric("Documents", db_metrics["document_count"])
        
        with col3:
            system_metrics = self._get_system_metrics()
            st.info("⚙️ System", icon="⚙️")
            st.metric("Memory Usage", f"{system_metrics['memory_usage']}%")
            st.metric("Uptime", system_metrics['uptime'])

        # Quick Actions
        st.subheader("🎯 Quick Actions")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Refresh Services"):
                st.rerun()
        with col2:
            if st.button("🗑 Clear Cache"):
                self._clear_cache()
        with col3:
            if st.button("📤 Export Logs"):
                self._export_logs()

    def render_services_tab(self):
        """Rendert den Services Tab mit detaillierten Service-Informationen."""
        st.header("🔌 Services")
        
        # Chat Service Details
        with st.expander("💬 Chat Service Details", expanded=True):
            chat_metrics = self.metrics.get_chat_metrics()
            if chat_metrics["status"] == "Active":
                self._render_chat_service_details(chat_metrics)
        
        # Database Service Details
        with st.expander("🗄 Database Service Details", expanded=True):
            db_metrics = self.metrics.get_db_metrics()
            if db_metrics["status"] == "Connected":
                self._render_database_service_details(db_metrics)

    def render_database_tab(self):
        """Rendert den Database Tab mit ChromaDB Insights."""
        st.header("🗄 Database Insights")
        
        db_metrics = self.metrics.get_db_metrics()
        if db_metrics["status"] != "Connected":
            st.error("Database not connected")
            return
            
        # Collection Stats
        st.subheader("Collection Statistics")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Documents", db_metrics["document_count"])
        with col2:
            st.metric("Collection Size", self._get_collection_size())
            
        # Document Types Distribution
        doc_types = self._get_document_types_distribution()
        if len(doc_types) > 0:
            fig = self._create_distribution_chart(doc_types)
            st.plotly_chart(fig, key="doc_types_dist")
        else:
            st.info("No document type distribution data available")

    def render_monitoring_tab(self):
        """Rendert den Monitoring Tab mit Logs und Performance Metriken."""
        st.header("📊 Monitoring")
        
        # Performance Metrics
        st.subheader("Performance")
        perf_metrics = self._get_performance_metrics()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Avg Response Time", f"{perf_metrics['avg_response_time']:.2f}s")
        with col2:
            st.metric("Success Rate", f"{perf_metrics['success_rate']:.1f}%")
        with col3:
            st.metric("Error Rate", f"{perf_metrics['error_rate']:.1f}%")
            
        # Response Times Chart
        response_times_df = self._get_response_times()
        if response_times_df is not None and not response_times_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=response_times_df["timestamp"],
                y=response_times_df["duration"],
                mode='lines+markers'
            ))
            fig.update_layout(
                title="Response Times",
                xaxis_title="Time",
                yaxis_title="Duration (s)"
            )
            st.plotly_chart(fig, key="monitoring_response_times")
        else:
            st.info("No response time data available")
            
        # Log Viewer
        st.subheader("Log Viewer")
        self._render_log_viewer()
        
    def render_debug_tab(self):
        """Rendert den Debug Tab mit Entwickler-Tools."""
        st.header("🛠 Debug Tools")
        
        # Debug Mode Toggle
        debug_mode = st.toggle("🐛 Debug Mode", value=st.session_state.get("debug_mode", False))
        if debug_mode != st.session_state.get("debug_mode"):
            st.session_state.debug_mode = debug_mode
            st.rerun()
            
        # System Information
        with st.expander("⚙️ System Information", expanded=True):
            st.code(json.dumps(self._get_system_info(), indent=2))
            
        # Session State Viewer
        with st.expander("🔍 Session State"):
            self._render_session_state()

    def _get_system_metrics(self) -> Dict[str, Any]:
        """Sammelt System-Metriken."""
        # Implementierung der System-Metrik-Sammlung
        return {
            "memory_usage": 45,  # Beispielwert
            "uptime": "2h 15m"   # Beispielwert
        }

    def _render_chat_service_details(self, metrics: Dict[str, Any]):
        """Rendert detaillierte Chat-Service-Informationen."""
        col1, col2 = st.columns(2)
        with col1:
            st.json({
                "Model": metrics["model"],
                "Temperature": metrics["temperature"],
                "Max Tokens": metrics["max_tokens"]
            })
        
        with col2:
            # Response Time Chart
            response_times_df = self._get_response_times()
            if response_times_df is not None and not response_times_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=response_times_df["timestamp"],
                    y=response_times_df["duration"],
                    mode='lines+markers'
                ))
                fig.update_layout(
                    title="Response Times",
                    xaxis_title="Time",
                    yaxis_title="Duration (s)"
                )
                st.plotly_chart(fig, key="service_response_times")
            else:
                st.info("No response time data available")

    def _render_database_service_details(self, metrics: Dict[str, Any]):
        """Rendert detaillierte Datenbank-Service-Informationen."""
        st.json({
            "Collection": metrics["collection"],
            "Document Count": metrics["document_count"],
            "Storage Location": metrics["persist_directory"]
        })

    def _get_collection_size(self) -> str:
        """Berechnet die Größe der Collection."""
        try:
            total_size = 0
            path = Path(settings.database.persist_directory)
            for file in path.rglob('*'):
                if file.is_file():
                    total_size += file.stat().st_size
            return f"{total_size / (1024*1024):.2f} MB"
        except Exception as e:
            self.logger.error(f"Error calculating collection size: {str(e)}")
            return "N/A"

    def _get_document_types_distribution(self) -> Dict[str, int]:
        """Ermittelt die Verteilung der Dokumenttypen."""
        try:
            retrieval_service = st.session_state.get("retrieval_service")
            if not retrieval_service or not hasattr(retrieval_service.db, "collection"):
                return {}
                
            collection = retrieval_service.db.collection
            results = collection.get()
            type_dist = {}
            for metadata in results['metadatas']:
                if metadata and 'type' in metadata:
                    type_dist[metadata['type']] = type_dist.get(metadata['type'], 0) + 1
            return type_dist
        except Exception as e:
            self.logger.error(f"Error getting document distribution: {str(e)}")
            return {}

    def _create_distribution_chart(self, data: Dict[str, int]):
        """Erstellt ein Verteilungsdiagramm."""
        fig = px.pie(values=list(data.values()), 
                    names=list(data.keys()),
                    title="Document Types Distribution")
        return fig

    def _get_performance_metrics(self) -> Dict[str, float]:
        """Sammelt Performance-Metriken."""
        metrics = st.session_state.get("metrics", {})
        total_msgs = metrics.get("messages_sent", 0)
        errors = metrics.get("errors_occurred", 0)
        
        if total_msgs == 0:
            return {
                "avg_response_time": 0.0,
                "success_rate": 100.0,
                "error_rate": 0.0
            }
            
        return {
            "avg_response_time": metrics.get("last_response_time", 0),
            "success_rate": ((total_msgs - errors) / total_msgs) * 100,
            "error_rate": (errors / total_msgs) * 100 if total_msgs > 0 else 0
        }

    def _get_response_times(self) -> Optional[pd.DataFrame]:
        """Sammelt Response-Zeit-Daten."""
        try:
            chat_history = st.session_state.get("chat_history", [])
            times = []
            durations = []
            
            for msg in chat_history:
                if (getattr(msg, 'role', None) == "assistant" and 
                    getattr(msg, 'metadata', None) and 
                    'timestamp' in msg.metadata):
                    times.append(datetime.fromisoformat(msg.metadata["timestamp"]))
                    durations.append(msg.metadata.get("response_time", 0))
                    
            if len(times) > 0 and len(durations) > 0:  # Änderung hier: explizite Längenprüfung
                return pd.DataFrame({
                    "timestamp": times,
                    "duration": durations
                })
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting response times: {str(e)}")
            return None
        
    def _render_log_viewer(self):
        """Rendert den erweiterten Log-Viewer."""
        # Log Level Filter
        col1, col2, col3 = st.columns([2,2,6])
        with col1:
            level = st.selectbox("Log Level", ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        with col2:
            source = st.selectbox("Source", ["ALL", "chat_service", "database", "document_processor"])
        with col3:
            st.toggle("Auto-Refresh", value=False)
            
        try:
            current_month = datetime.now().strftime("%Y-%m")
            log_path = Path("logs") / current_month / "app.log"
            
            if log_path.exists():
                with log_path.open() as f:
                    logs = f.readlines()[-100:]  # Last 100 lines
                    
                filtered_logs = []
                for log in logs:
                    if (level == "ALL" or f"[{level}]" in log) and \
                       (source == "ALL" or source in log):
                        filtered_logs.append(log)
                
                if filtered_logs:
                    st.code("".join(filtered_logs))
                else:
                    st.info("No matching logs found")
            else:
                st.warning(f"No log file found at {log_path}")
                
        except Exception as e:
            st.error(f"Error reading logs: {str(e)}")

    def _get_system_info(self) -> Dict[str, Any]:
        """Sammelt System-Informationen."""
        return {
            "Environment": settings.environment,
            "Debug Mode": settings.debug,
            "Services": {
                "Chat Service": {
                    "Status": "Active" if st.session_state.get("chat_service") else "Inactive",
                    "Model": settings.api.openai_model,
                    "Temperature": settings.chat.temperature
                },
                "Database": {
                    "Status": "Connected" if st.session_state.get("retrieval_service") else "Disconnected",
                    "Collection": settings.database.collection_name,
                    "Persist Directory": settings.database.persist_directory
                }
            },
            "Logging": {
                "Log Level": settings.logging.log_level,
                "Debug Mode": settings.logging.debug_mode,
                "Performance Logging": settings.logging.enable_performance_logging
            }
        }

    def _render_session_state(self):
        """Rendert einen gefilterten Session State Viewer."""
        # Sensitive und interne Daten filtern
        filtered_state = {}
        for key, value in st.session_state.items():
            # Komplexe Objekte und sensitive Daten ausschließen
            if not isinstance(value, (bytes, type(lambda: None))) and \
               not str(key).startswith('_') and \
               key not in ['password', 'token', 'api_key']:
                filtered_state[key] = str(value) if isinstance(value, (datetime, timedelta)) else value
        
        st.json(filtered_state)

    def _clear_cache(self):
        """Bereinigt den Cache und Session State."""
        try:
            # Basis-Session-Informationen speichern
            session_id = st.session_state.get("session_id")
            debug_mode = st.session_state.get("debug_mode")
            
            # Session State zurücksetzen
            st.session_state.clear()
            
            # Wichtige Basis-Informationen wiederherstellen
            st.session_state.session_id = session_id
            st.session_state.debug_mode = debug_mode
            
            st.success("Cache successfully cleared!")
            
            # Services neu initialisieren
            asyncio.run(StateManager().initialize())
            
        except Exception as e:
            st.error(f"Error clearing cache: {str(e)}")
            self.logger.error(f"Cache clearing failed: {str(e)}")

    def _export_logs(self):
        """Exportiert die aktuellen Logs."""
        try:
            current_month = datetime.now().strftime("%Y-%m")
            log_path = Path("logs") / current_month / "app.log"
            
            if log_path.exists():
                with log_path.open("r") as f:
                    logs = f.read()
                
                # Download-Button für Logs
                st.download_button(
                    label="📥 Download Logs",
                    data=logs,
                    file_name=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                    mime="text/plain"
                )
            else:
                st.warning("No logs found to export")
                
        except Exception as e:
            st.error(f"Error exporting logs: {str(e)}")
            self.logger.error(f"Log export failed: {str(e)}")


class DeveloperDashboard:
    """Hauptklasse für das Developer Dashboard."""
    
    def __init__(self):
        """Initialisiert das Developer Dashboard."""
        self.tabs = DashboardTabs()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
    async def render(self):
        """Rendert das komplette Dashboard."""
        try:
            # Seiten-Konfiguration
            st.set_page_config(
                page_title="Developer Dashboard - Fahrzeugexperten-Chatbot",
                page_icon="📊",
                layout="wide"
            )

            # Titel und Beschreibung
            st.title("📊 Developer Dashboard")
            st.markdown("Monitoring und Debug-Interface für den Fahrzeugexperten-Chatbot")

            # Tab-Auswahl
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📈 Overview",
                "🔌 Services",
                "🗄 Database",
                "📊 Monitoring",
                "🛠 Debug"
            ])

            # Tab-Inhalte rendern
            with tab1:
                self.tabs.render_overview_tab()
            with tab2:
                self.tabs.render_services_tab()
            with tab3:
                self.tabs.render_database_tab()
            with tab4:
                self.tabs.render_monitoring_tab()
            with tab5:
                self.tabs.render_debug_tab()

        except Exception as e:
            st.error("🚫 Error loading dashboard")
            if st.session_state.get("debug_mode"):
                st.exception(e)
            self.logger.error(f"Dashboard rendering failed: {str(e)}")


# Dashboard-Instanz erstellen und rendern wenn Skript direkt ausgeführt wird
if __name__ == "__main__":
    dashboard = DeveloperDashboard()
    asyncio.run(dashboard.render())