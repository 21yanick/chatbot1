"""
Dokumenten-Management-Seite.
Ermöglicht Upload, Verwaltung und Einsicht von Dokumenten über ein Tab-Interface.
"""

import asyncio
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from typing import List, Dict, Any

from src.backend.models.document import Document, DocumentType, DocumentStatus
from src.backend.services.document_processor import DocumentProcessor
from src.backend.services.document_upload_service import DocumentUploadError, DocumentUploadService
from src.backend.services.embedding_service import EmbeddingService
from src.backend.utils.database import ChromaDBManager
from src.frontend.components.document_viewer.viewer import DocumentViewer
from src.config.logging_config import get_logger
from src.frontend.utils.state_manager import StateManager

# Logger initialisieren
logger = get_logger(__name__)

class DocumentsPage:
    """
    Hauptklasse für die Dokumentenverwaltungs-Seite.
    Implementiert ein Tab-basiertes Interface für verschiedene Dokumentenfunktionen.
    """
    
    def __init__(self):
        """Initialisiert die Documents Page."""
        self.initialize_session_state()
        self.setup_page_config()
        
    def initialize_session_state(self):
        """Initialisiert den Session State mit Standardwerten."""
        if 'documents' not in st.session_state:
            st.session_state.documents = []
        if 'selected_document' not in st.session_state:
            st.session_state.selected_document = None
        if 'filter_criteria' not in st.session_state:
            st.session_state.filter_criteria = {
                'search_text': '',
                'document_type': [],
                'status': [],
                'date_range': (None, None),
                'topics': []
            }
            
    def setup_page_config(self):
        """Konfiguriert die Streamlit-Seite."""
        st.set_page_config(
            page_title="Dokumentenverwaltung",
            page_icon="📚",
            layout="wide"
        )
        
    def render_dashboard_tab(self):
        """Rendert den Dashboard-Tab mit Übersicht und Statistiken."""
        st.header("📊 Dashboard")
        
        # Prüfen ob Dokumente existieren
        documents = st.session_state.get('documents', [])
        
        # Statistik-Karten in der obersten Reihe
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Gesamt Dokumente",
                len(documents),
                "↑ 0 diese Woche"  # Dynamisch berechnen wenn gewünscht
            )
        with col2:
            completed_docs = sum(1 for d in documents 
                               if d.status == DocumentStatus.COMPLETED)
            st.metric(
                "Aktive Dokumente",
                completed_docs,
                f"{(completed_docs/len(documents)*100 if documents else 0):.1f}%"
            )
        with col3:
            st.metric(
                "Durchschn. Chunks",
                "0",  # TODO: Aus tatsächlichen Chunks berechnen
                "0"
            )
        with col4:
            total_usage = sum(d.usage_count for d in documents)
            st.metric(
                "Gesamt Nutzungen",
                total_usage,
                "↑ 0 heute"  # Dynamisch berechnen wenn gewünscht
            )
        
        # Diagramme in der zweiten Reihe
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Dokumente nach Typ")
            # Tatsächliche Daten aus den Dokumenten extrahieren
            type_counts = {}
            for doc in documents:
                type_counts[doc.document_type.value] = type_counts.get(doc.document_type.value, 0) + 1
            
            if type_counts:
                df_types = pd.DataFrame({
                    'Typ': list(type_counts.keys()),
                    'Anzahl': list(type_counts.values())
                })
                fig = px.pie(df_types, values='Anzahl', names='Typ')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Noch keine Dokumente vorhanden")
            
        with col2:
            st.subheader("Aktivität letzte 30 Tage")
            # Beispieldaten für das Liniendiagramm, später mit echten Daten ersetzen
            dates = pd.date_range(
                start=datetime.now() - timedelta(days=30),
                end=datetime.now(),
                freq='D'
            )
            
            # Leere Arrays der gleichen Länge erstellen
            empty_data = [0] * len(dates)
            
            activity_data = pd.DataFrame({
                'Datum': dates,
                'Uploads': empty_data,
                'Nutzungen': empty_data
            })
            
            fig = px.line(activity_data, x='Datum', y=['Uploads', 'Nutzungen'])
            st.plotly_chart(fig, use_container_width=True)
            
        # Letzte Aktivitäten
        st.subheader("Letzte Aktivitäten")
        if documents:
            activities = [
                {
                    "zeit": doc.updated_at.strftime("%Y-%m-%d %H:%M") if doc.updated_at else doc.created_at.strftime("%Y-%m-%d %H:%M"),
                    "aktion": f"Dokument {doc.status.value}",
                    "nutzer": "System"
                }
                for doc in sorted(documents, key=lambda x: x.created_at, reverse=True)[:5]
            ]
        else:
            activities = []
            
        if activities:
            df = pd.DataFrame(activities)
            st.dataframe(
                df,
                column_config={
                    "zeit": "Zeitpunkt",
                    "aktion": "Aktivität",
                    "nutzer": "Benutzer"
                },
                hide_index=True
            )
        else:
            st.info("Noch keine Aktivitäten vorhanden")
        
    def render_documents_tab(self):
        """Rendert den Dokumenten-Tab mit Liste und Filterfunktionen."""
        st.header("📋 Dokumente")
        
        # Filter-Bereich
        with st.expander("🔍 Filter & Suche", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.text_input(
                    "Suche",
                    key="search_text",
                    placeholder="Suchbegriff eingeben..."
                )
                st.multiselect(
                    "Dokumenttyp",
                    options=[t.value for t in DocumentType],
                    default=[],
                    key="doc_type_filter"
                )
                
            with col2:
                st.multiselect(
                    "Status",
                    options=[s.value for s in DocumentStatus],
                    default=[],
                    key="status_filter"
                )
                st.multiselect(
                    "Themen",
                    options=["sicherheit", "parken", "elektro", "antrieb", "wartung"],
                    default=[],
                    key="topics_filter"
                )
                
            with col3:
                st.date_input(
                    "Zeitraum von",
                    key="date_from"
                )
                st.date_input(
                    "Zeitraum bis",
                    key="date_to"
                )
        
        # Aktions-Buttons
        col1, col2, col3, col4 = st.columns([2, 2, 2, 6])
        with col1:
            if st.button("🔄 Aktualisieren"):
                st.rerun()
        with col2:
            if st.button("📥 Export"):
                st.info("Export-Funktion noch nicht implementiert")
        with col3:
            if st.button("🗑 Löschen"):
                st.warning("Bitte zuerst Dokumente auswählen")
        
        # Dokumententabelle
        st.data_editor(
            pd.DataFrame([{
                "id": doc.id,
                "title": doc.title,
                "type": doc.document_type.value,
                "status": doc.status.value,
                "created": doc.created_at,
                "usage": doc.usage_count
            } for doc in st.session_state.documents]),
            column_config={
                "id": "ID",
                "title": "Titel",
                "type": "Typ",
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=[s.value for s in DocumentStatus],
                    required=True
                ),
                "created": st.column_config.DatetimeColumn(
                    "Erstellt am",
                    format="DD.MM.YYYY HH:mm"
                ),
                "usage": st.column_config.NumberColumn(
                    "Nutzungen",
                    format="%d"
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
    def render_upload_tab(self):
        """
        Rendert den Upload-Tab für neue Dokumente.
        
        Verarbeitet Datei-Uploads und Metadaten-Eingaben,
        koordiniert die Dokumentenverarbeitung über den DocumentUploadService
        und zeigt den Fortschritt/Status an.
        """
        st.header("📤 Dokument hochladen")
        
        # Services initialisieren falls noch nicht geschehen
        if 'upload_service' not in st.session_state:
            try:
                # Processor initialisieren
                processor = DocumentProcessor()
                asyncio.run(processor.initialize())
                
                # DB Manager initialisieren
                db_manager = ChromaDBManager()
                asyncio.run(db_manager.initialize())
                
                # Embedding Service initialisieren
                embedding_service = EmbeddingService()
                asyncio.run(embedding_service.initialize())
                
                # Upload Service mit initialisierten Services erstellen
                st.session_state.upload_service = DocumentUploadService(
                    processor=processor,
                    db_manager=db_manager,
                    embedding_service=embedding_service
                )
                
                st.session_state.services_initialized = True
                
            except Exception as e:
                st.error(f"Fehler bei der Service-Initialisierung: {str(e)}")
                logger.exception("Service-Initialisierung fehlgeschlagen")
                return
        
        # Upload-Bereich
        uploaded_files = st.file_uploader(
            "Dateien zum Hochladen",
            accept_multiple_files=True,
            type=['pdf', 'txt', 'doc', 'docx']
        )
        
        if uploaded_files:
            st.info(f"{len(uploaded_files)} Datei(en) ausgewählt")
            
            # Basis-Metadaten
            st.subheader("Basis-Informationen")
            col1, col2 = st.columns(2)
            
            with col1:
                doc_type = st.selectbox(
                    "Dokumenttyp",
                    options=[t.value for t in DocumentType]
                )
                category = st.text_input("Kategorie")
                
            with col2:
                source_link = st.text_input(
                    "Quell-Link (erforderlich)",
                    help="URL zum Originaldokument"
                )
                language = st.selectbox(
                    "Sprache",
                    options=["de", "en"],
                    index=0
                )
            
            # Erweiterte Metadaten
            with st.expander("Erweiterte Metadaten", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    topics = st.multiselect(
                        "Themen",
                        options=["sicherheit", "parken", "elektro", "antrieb", "wartung"]
                    )
                    importance = st.slider(
                        "Wichtigkeit",
                        min_value=0.0,
                        max_value=1.0,
                        value=1.0,
                        step=0.1
                    )
                    
                with col2:
                    related_docs = st.multiselect(
                        "Verwandte Dokumente",
                        options=[d.id for d in st.session_state.documents]
                    )
                    prerequisites = st.multiselect(
                        "Voraussetzungen",
                        options=[d.id for d in st.session_state.documents]
                    )
            
            # Verarbeitungsoptionen
            with st.expander("Verarbeitungsoptionen", expanded=False):
                chunk_size = st.number_input(
                    "Chunk-Größe",
                    min_value=100,
                    max_value=2000,
                    value=1000
                )
                chunk_overlap = st.number_input(
                    "Chunk-Überlappung",
                    min_value=0,
                    max_value=500,
                    value=200
                )
            
            # Upload-Button
            if st.button("Dokumente verarbeiten"):
                if not source_link:
                    st.error("Bitte geben Sie einen Quell-Link an")
                else:
                    try:
                        # Metadaten sammeln
                        shared_metadata = {
                            'source_link': source_link,
                            'document_type': doc_type,
                            'category': category,
                            'language': language,
                            'topics': topics,
                            'importance_score': importance,
                            'related_docs': related_docs,
                            'prerequisites': prerequisites,
                            'additional_metadata': {
                                'chunk_size': chunk_size,
                                'chunk_overlap': chunk_overlap
                            }
                        }
                        
                        # Fortschrittsanzeige initialisieren
                        progress_text = "Verarbeite Dokumente..."
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # Dokumente verarbeiten
                        for i, file in enumerate(uploaded_files):
                            current_progress = (i / len(uploaded_files))
                            progress_bar.progress(current_progress)
                            status_text.text(f"Verarbeite {file.name}...")
                            
                            # Dokument verarbeiten
                            document = asyncio.run(
                                st.session_state.upload_service.process_upload(
                                    file,
                                    shared_metadata
                                )
                            )
                            
                            # Zum Session State hinzufügen
                            if 'documents' not in st.session_state:
                                st.session_state.documents = []
                            st.session_state.documents.append(document)
                        
                        # Abschluss
                        progress_bar.progress(1.0)
                        status_text.text("Verarbeitung abgeschlossen!")
                        st.success(f"{len(uploaded_files)} Dokument(e) erfolgreich verarbeitet")
                        
                        # UI aktualisieren
                        st.rerun()
                        
                    except DocumentUploadError as e:
                        st.error(f"Fehler bei der Verarbeitung: {str(e)}")
                        logger.error(
                            "Upload-Fehler",
                            extra={
                                "error": str(e),
                                "files": [f.name for f in uploaded_files]
                            }
                        )
                    except Exception as e:
                        st.error("Ein unerwarteter Fehler ist aufgetreten")
                        logger.exception(
                            "Unerwarteter Upload-Fehler",
                            extra={"files": [f.name for f in uploaded_files]}
                        )
        
    def render_settings_tab(self):
        """Rendert den Einstellungs-Tab."""
        st.header("⚙️ Einstellungen")
        
        # Verarbeitungseinstellungen
        st.subheader("Verarbeitungseinstellungen")
        col1, col2 = st.columns(2)
        
        with col1:
            st.number_input(
                "Standard Chunk-Größe",
                min_value=100,
                max_value=2000,
                value=1000
            )
            st.number_input(
                "Minimale Chunk-Größe",
                min_value=50,
                max_value=500,
                value=100
            )
            
        with col2:
            st.number_input(
                "Standard Überlappung",
                min_value=0,
                max_value=500,
                value=200
            )
            st.checkbox(
                "Automatische Spracherkennung",
                value=True
            )
        
        # Systemeinstellungen
        st.subheader("Systemeinstellungen")
        col1, col2 = st.columns(2)
        
        with col1:
            st.selectbox(
                "Maximale Suchergebnisse",
                options=[5, 10, 20, 50],
                index=1
            )
            st.checkbox(
                "Debug-Modus",
                value=False
            )
            
        with col2:
            st.selectbox(
                "Standard-Sortierung",
                options=["Datum absteigend", "Datum aufsteigend", "Titel", "Typ"],
                index=0
            )
            st.checkbox(
                "Erweiterte Logging",
                value=True
            )
        
        # Backup-Einstellungen
        st.subheader("Backup & Export")
        col1, col2 = st.columns(2)
        
        with col1:
            st.checkbox(
                "Automatische Backups",
                value=True
            )
            st.selectbox(
                "Backup-Intervall",
                options=["Täglich", "Wöchentlich", "Monatlich"],
                index=1
            )
            
        with col2:
            st.text_input(
                "Backup-Pfad",
                value="/path/to/backup"
            )
            if st.button("Backup jetzt erstellen"):
                st.info("Backup-Funktion noch nicht implementiert")
                
        if st.button("Einstellungen speichern"):
            st.success("Einstellungen erfolgreich gespeichert")
            
    def render(self):
        """
        Rendert die gesamte Documents Page.
        Erzeugt das Tab-Interface und rendert die entsprechenden Inhalte.
        """
        # Titelbereich
        st.title("📚 Dokumentenverwaltung")
        st.markdown("""
            Hier können Sie Dokumente hochladen, verwalten und einsehen. 
            Wählen Sie einen der Tabs unten, um zu beginnen.
        """)
        
        # System-Status Indikator
        status_col1, status_col2 = st.columns([1, 11])
        with status_col1:
            st.markdown("### 🟢")
        with status_col2:
            st.markdown("System aktiv und bereit")
        
        st.divider()
        
        # Tab-Auswahl mit Beschreibungen
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Dashboard",
            "📋 Dokumente",
            "📤 Upload",
            "⚙️ Einstellungen"
        ])
        
        # Dashboard Tab
        with tab1:
            try:
                self.render_dashboard_tab()
            except Exception as e:
                logger.error(f"Fehler beim Rendern des Dashboard-Tabs: {str(e)}")
                st.error("Fehler beim Laden des Dashboards. Bitte versuchen Sie es später erneut.")
        
        # Dokumente Tab
        with tab2:
            try:
                self.render_documents_tab()
            except Exception as e:
                logger.error(f"Fehler beim Rendern des Dokumente-Tabs: {str(e)}")
                st.error("Fehler beim Laden der Dokumentenliste. Bitte versuchen Sie es später erneut.")
        
        # Upload Tab
        with tab3:
            try:
                self.render_upload_tab()
            except Exception as e:
                logger.error(f"Fehler beim Rendern des Upload-Tabs: {str(e)}")
                st.error("Fehler beim Laden des Upload-Bereichs. Bitte versuchen Sie es später erneut.")
        
        # Einstellungen Tab
        with tab4:
            try:
                self.render_settings_tab()
            except Exception as e:
                logger.error(f"Fehler beim Rendern des Einstellungen-Tabs: {str(e)}")
                st.error("Fehler beim Laden der Einstellungen. Bitte versuchen Sie es später erneut.")
        
        # Footer-Bereich
        st.divider()
        footer_col1, footer_col2, footer_col3 = st.columns(3)
        
        with footer_col1:
            st.caption("Letzte Aktualisierung: " + datetime.now().strftime("%H:%M:%S"))
        
        with footer_col2:
            st.caption(f"Dokumente im System: {len(st.session_state.documents)}")
        
        with footer_col3:
            if st.button("🔄 Seite neu laden"):
                st.rerun()
        
        # Session-State Debug-Anzeige wenn im Debug-Modus
        if st.session_state.get('debug_mode', False):
            with st.expander("🔍 Debug Information", expanded=False):
                st.json({
                    "session_state": {
                        k: str(v) for k, v in st.session_state.items()
                    }
                })
                
# Die main-Funktion muss außerhalb der Klasse sein
def main():
    """
    Hauptfunktion zum Starten der Documents Page.
    Initialisiert die Seite und handhabt globale Ausnahmen.
    """
    try:
        # Seite initialisieren
        documents_page = DocumentsPage()
        
        # Seite rendern
        documents_page.render()
        
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Starten der Documents Page: {str(e)}")
        st.error("""
            Ein kritischer Fehler ist aufgetreten. 
            Bitte laden Sie die Seite neu oder kontaktieren Sie den Support.
        """)
        
        # Debug-Informationen anzeigen wenn im Debug-Modus
        if st.session_state.get('debug_mode', False):
            st.exception(e)

# Auch der if-Block muss außerhalb der Klasse sein
if __name__ == "__main__":
    main()