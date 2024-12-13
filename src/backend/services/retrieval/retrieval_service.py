"""
Retrieval-Service-Modul.
Zentrale Komponente für Dokumenten-Retrieval und -Management.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    log_function_call
)
from src.backend.models.document import Document
from src.backend.interfaces.retrieval import RetrievalService, RetrievalServiceError
from src.backend.services.embedding_service import EmbeddingService
from src.backend.utils.database import ChromaDBManager
from .factories.document_factory import DocumentFactory
from .managers.cache_manager import CacheManager
from .managers.metadata_manager import MetadataManager
from .utils.result_processor import ResultProcessor
from .utils.validators import DocumentValidator

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class RetrievalServiceImpl(RetrievalService):
    """
    Implementierung des Retrieval-Services mit optimierter Struktur.
    
    Diese Version nutzt spezialisierte Komponenten für:
    - Dokumentenerstellung und -validierung
    - Cache-Management
    - Metadaten-Verarbeitung
    - Ergebnisverarbeitung
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        db_manager: Optional[ChromaDBManager] = None,
        cache_size: int = 1000
    ):
        """
        Initialisiert den Retrieval-Service.
        
        Args:
            embedding_service: Service für Embedding-Generierung
            db_manager: Optionaler ChromaDB-Manager
            cache_size: Größe des Dokument-Caches
        """
        super().__init__()
        
        # Kernkomponenten
        self.embedding_service = embedding_service
        self.db = db_manager or ChromaDBManager()
        
        # Hilfskomponenten initialisieren
        self.document_factory = DocumentFactory()
        self.cache_manager = CacheManager(max_size=cache_size)
        self.metadata_manager = MetadataManager()
        self.result_processor = ResultProcessor(DocumentValidator())
        
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """Initialisiert den Service und seine Abhängigkeiten."""
        try:
            with log_execution_time(self.logger, "service_initialization"):
                await self.embedding_service.initialize()
                await self.db.initialize()
                
            self.logger.info("Retrieval-Service initialisiert")
            
        except Exception as e:
            log_error_with_context(
                self.logger,
                e,
                {},
                "Fehler bei Service-Initialisierung"
            )
            raise RetrievalServiceError(f"Initialisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Service-Ressourcen."""
        try:
            with log_execution_time(self.logger, "service_cleanup"):
                await self.embedding_service.cleanup()
                await self.db.cleanup()
                await self.cache_manager.clear()
            
            self.logger.info("Service-Ressourcen bereinigt")
            
        except Exception as e:
            self.logger.error(f"Fehler bei Ressourcenbereinigung: {str(e)}")
    
    @log_function_call(logger)
    async def add_document(self, document: Document) -> Document:
        """
        Fügt ein Dokument zum System hinzu.
        
        Args:
            document: Hinzuzufügendes Dokument
            
        Returns:
            Verarbeitetes Dokument
            
        Raises:
            RetrievalServiceError: Bei Fehlern beim Hinzufügen
        """
        try:
            # Metadaten extrahieren und hinzufügen
            metadata = await self.metadata_manager.extract_metadata(document.content)
            document.metadata.update(metadata)
            
            # Embedding generieren
            embedding = await self.embedding_service.get_embedding(document.content)
            
            # In ChromaDB speichern
            await self.db.add_documents(
                ids=[document.id],
                embeddings=[embedding],
                documents=[document.content],
                metadatas=[document.metadata]
            )
            
            # Im Cache speichern
            await self.cache_manager.put(document)
            
            self.logger.info(
                "Dokument hinzugefügt",
                extra={
                    "document_id": document.id,
                    "content_length": len(document.content)
                }
            )
            return document
            
        except Exception as e:
            error_context = {
                "document_id": document.id,
                "content_length": len(document.content)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Hinzufügen eines Dokuments"
            )
            raise RetrievalServiceError(f"Dokument konnte nicht hinzugefügt werden: {str(e)}")
    
    @log_function_call(logger)
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        Ruft ein Dokument ab.
        
        Args:
            document_id: ID des gewünschten Dokuments
            
        Returns:
            Gefundenes Dokument oder None
        """
        try:
            # Cache überprüfen
            if cached_doc := await self.cache_manager.get(document_id):
                return cached_doc
            
            # Aus Datenbank abrufen
            results = await self.db.query(
                query_embeddings=[],
                where={"original_id": document_id}
            )
            
            if not results or not results.get('documents'):
                self.logger.warning(
                    "Dokument nicht gefunden",
                    extra={"document_id": document_id}
                )
                return None
            
            # Dokument rekonstruieren
            document = await self.result_processor.process_chunk_results(
                results,
                document_id
            )
            
            if document:
                await self.cache_manager.put(document)
                
            return document
            
        except Exception as e:
            error_context = {"document_id": document_id}
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Dokumentenabruf"
            )
            raise RetrievalServiceError(f"Dokument konnte nicht abgerufen werden: {str(e)}")
    
    @log_function_call(logger)
    async def search_documents(
        self,
        query: str,
        limit: int = 3,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Sucht nach Dokumenten.
        
        Args:
            query: Suchanfrage
            limit: Maximale Anzahl Ergebnisse
            metadata_filter: Optionaler Metadaten-Filter
            
        Returns:
            Liste gefundener Dokumente
        """
        try:
            # Embedding für Suchanfrage generieren
            query_embedding = await self.embedding_service.get_embedding(query)
            
            # Suche durchführen
            results = await self.db.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=metadata_filter
            )
            
            # Ergebnisse verarbeiten
            documents = await self.result_processor.process_search_results(
                results,
                include_scores=True
            )
            
            self.logger.info(
                "Dokumentensuche durchgeführt",
                extra={
                    "query_length": len(query),
                    "results_count": len(documents)
                }
            )
            return documents
            
        except Exception as e:
            error_context = {
                "query_length": len(query),
                "limit": limit
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei der Dokumentensuche"
            )
            raise RetrievalServiceError(f"Suche fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def delete_document(self, document_id: str) -> bool:
        """
        Löscht ein Dokument.
        
        Args:
            document_id: ID des zu löschenden Dokuments
            
        Returns:
            True wenn erfolgreich gelöscht
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                return False
            
            # Aus der Datenbank löschen
            await self.db.delete([document_id])
            
            # Aus dem Cache entfernen
            await self.cache_manager.remove(document_id)
            
            self.logger.info(
                "Dokument gelöscht",
                extra={"document_id": document_id}
            )
            return True
            
        except Exception as e:
            error_context = {"document_id": document_id}
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Dokumentenlöschen"
            )
            raise RetrievalServiceError(f"Löschen fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def update_document(
        self,
        document_id: str,
        document: Document
    ) -> Optional[Document]:
        """
        Aktualisiert ein Dokument.
        
        Args:
            document_id: ID des zu aktualisierenden Dokuments
            document: Neues Dokument
            
        Returns:
            Aktualisiertes Dokument oder None
        """
        try:
            # Altes Dokument löschen
            await self.delete_document(document_id)
            
            # Neues Dokument hinzufügen
            updated_doc = await self.add_document(document)
            
            self.logger.info(
                "Dokument aktualisiert",
                extra={
                    "document_id": document_id,
                    "content_length": len(document.content)
                }
            )
            return updated_doc
            
        except Exception as e:
            error_context = {
                "document_id": document_id,
                "content_length": len(document.content)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumentenaktualisierung"
            )
            raise RetrievalServiceError(f"Aktualisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def get_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        Findet ähnliche Dokumente.
        
        Args:
            document_id: ID des Referenzdokuments
            limit: Maximale Anzahl Ergebnisse
            score_threshold: Minimaler Ähnlichkeitsscore
            
        Returns:
            Liste ähnlicher Dokumente
        """
        try:
            document = await self.get_document(document_id)
            if not document:
                return []
            
            # Ähnlichkeitssuche durchführen
            similar_docs = await self.search_documents(
                query=document.content,
                limit=limit + 1  # +1 für das Dokument selbst
            )
            
            # Originaldokument ausfiltern
            filtered_docs = [
                doc for doc in similar_docs 
                if doc.id != document_id
            ]
            
            # Score-Filter anwenden
            if score_threshold is not None:
                filtered_docs = [
                    doc for doc in filtered_docs
                    if doc.metadata.get("search_score", 0) >= score_threshold
                ]
            
            self.logger.info(
                "Ähnliche Dokumente gefunden",
                extra={
                    "reference_id": document_id,
                    "found_count": len(filtered_docs)
                }
            )
            return filtered_docs
            
        except Exception as e:
            error_context = {
                "document_id": document_id,
                "limit": limit
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Ähnlichkeitssuche"
            )
            raise RetrievalServiceError(f"Ähnlichkeitssuche fehlgeschlagen: {str(e)}")