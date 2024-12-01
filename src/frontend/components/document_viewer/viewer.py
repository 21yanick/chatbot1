"""
Document Viewer Modul - Komponente zur Anzeige und Verwaltung von Dokumenten

Diese Komponente bietet eine interaktive Oberfläche für:
- Dokumentenanzeige und Navigation
- Metadaten-Anzeige
- Quellennachweise im Chat-Kontext
- Debug-Informationen für Entwickler
"""

import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.backend.models.document import Document
from src.backend.services.retrieval_service import RetrievalServiceImpl
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

class DocumentViewer:
    """
    Komponente zur Anzeige und Verwaltung von Dokumenten.
    
    Bietet eine interaktive Oberfläche zur Dokumentenanzeige mit:
    - Dokumentnavigation
    - Metadatenanzeige
    - Quellenreferenzen
    """
    
    def __init__(self, retrieval_service: RetrievalServiceImpl):
        """
        Initialisiert den Document Viewer.
        
        Args:
            retrieval_service: Service für Dokumentenzugriff
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.retrieval_service = retrieval_service
        
        # Viewer-Status initialisieren
        if "selected_document_id" not in st.session_state:
            st.session_state.selected_document_id = None
        if "document_cache" not in st.session_state:
            st.session_state.document_cache = {}
    
    @log_function_call(logger)
    async def _load_document(self, document_id: str) -> Optional[Document]:
        """
        Lädt ein Dokument aus dem Cache oder Service.
        
        Args:
            document_id: ID des zu ladenden Dokuments
            
        Returns:
            Optional[Document]: Geladenes Dokument oder None bei Fehler
        """
        try:
            with log_execution_time(self.logger, "document_loading"):
                # Cache prüfen
                if document_id in st.session_state.document_cache:
                    self.logger.debug(
                        "Dokument aus Cache geladen",
                        extra={
                            "document_id": document_id,
                            "session_id": st.session_state.get("session_id")
                        }
                    )
                    return st.session_state.document_cache[document_id]
                
                # Dokument laden
                document = await self.retrieval_service.get_document(document_id)
                if document:
                    # In Cache speichern
                    st.session_state.document_cache[document_id] = document
                    self.logger.info(
                        "Dokument geladen und gecached",
                        extra={
                            "document_id": document_id,
                            "content_length": len(document.content)
                        }
                    )
                    return document
                
                return None
            
        except Exception as e:
            error_context = {
                "document_id": document_id,
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Laden des Dokuments"
            )
            return None
    
    def _render_metadata(self, document: Document) -> None:
        """
        Rendert die Metadaten eines Dokuments.
        
        Args:
            document: Anzuzeigendes Dokument
        """
        with st.expander("📋 Metadaten", expanded=False):
            metadata = document.metadata or {}
            
            # Basis-Metadaten
            st.markdown("#### Dokumentinformationen")
            st.markdown(f"""
                - **ID:** `{document.id}`
                - **Quelle:** {metadata.get('source', 'Nicht angegeben')}
                - **Typ:** {metadata.get('type', 'Nicht angegeben')}
                - **Erstellt:** {metadata.get('created_at', 'Unbekannt')}
            """)
            
            # Erweiterte Metadaten im Debug-Modus
            if st.session_state.get("debug_mode"):
                st.markdown("#### Debug-Informationen")
                st.json(metadata)
    
    def _render_content(self, document: Document) -> None:
        """
        Rendert den Dokumentinhalt.
        
        Args:
            document: Anzuzeigendes Dokument
        """
        st.markdown("### 📄 Dokumentinhalt")
        
        # Content-Container mit Scrolling
        st.markdown(
            f"""
            <div style="
                max-height: 400px;
                overflow-y: auto;
                padding: 1rem;
                border-radius: 0.5rem;
                background-color: white;
                border: 1px solid #ddd;
            ">
                {document.content}
            </div>
            """,
            unsafe_allow_html=True
        )
    
    @log_function_call(logger)
    async def render_document(self, document_id: str) -> None:
        """
        Rendert ein einzelnes Dokument.
        
        Args:
            document_id: ID des anzuzeigenden Dokuments
        """
        try:
            # Dokument laden
            document = await self._load_document(document_id)
            if not document:
                st.warning(f"Dokument nicht gefunden: {document_id}")
                return
            
            # Container für Dokument
            with st.container():
                # Navigation und Metadaten
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"### 📑 Dokument: {document_id}")
                
                with col2:
                    if st.button("🔄 Neu laden", key=f"reload_{document_id}"):
                        # Cache für dieses Dokument löschen
                        st.session_state.document_cache.pop(document_id, None)
                        self.logger.info(
                            "Cache für Dokument gelöscht",
                            extra={"document_id": document_id}
                        )
                        st.rerun()
                
                # Metadaten und Inhalt
                self._render_metadata(document)
                self._render_content(document)
                
                self.logger.debug(
                    "Dokument gerendert",
                    extra={
                        "document_id": document_id,
                        "session_id": st.session_state.get("session_id")
                    }
                )
            
        except Exception as e:
            error_context = {
                "document_id": document_id,
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern des Dokuments"
            )
            st.error(
                "🚫 Fehler beim Anzeigen des Dokuments. "
                "Bitte versuchen Sie es erneut."
            )
    
    @log_function_call(logger)
    async def render(self, document_ids: Optional[List[str]] = None) -> None:
        """
        Rendert den Document Viewer.
        
        Args:
            document_ids: Optionale Liste von anzuzeigenden Dokument-IDs
        """
        try:
            with st.container():
                st.markdown("## 📚 Dokumente")
                
                if not document_ids:
                    st.info("Keine Dokumente zum Anzeigen ausgewählt.")
                    return
                
                # Dokumente nacheinander anzeigen
                for doc_id in document_ids:
                    with st.expander(f"📄 Dokument: {doc_id}", expanded=True):
                        await self.render_document(doc_id)
                
                self.logger.info(
                    "Document Viewer gerendert",
                    extra={
                        "document_count": len(document_ids),
                        "session_id": st.session_state.get("session_id")
                    }
                )
                
        except Exception as e:
            error_context = {
                "document_count": len(document_ids) if document_ids else 0,
                "session_id": st.session_state.get("session_id")
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Rendern des Viewers"
            )
            st.error(
                "🚫 Fehler beim Laden der Dokumente. "
                "Bitte versuchen Sie es später erneut."
            )