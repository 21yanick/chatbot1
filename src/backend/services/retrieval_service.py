"""
Retrieval-Service-Modul.
Verantwortlich für die semantische Suche und Verwaltung von Dokumenten
mit ChromaDB-Integration.
"""

from typing import List, Dict, Any, Optional
import asyncio
from functools import lru_cache

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..models.document import Document
from ..interfaces.retrieval import RetrievalService, RetrievalServiceError
from .embedding_service import EmbeddingService
from .document_processor import DocumentProcessor
from ..utils.database import ChromaDBManager

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class RetrievalServiceImpl(RetrievalService):
    """
    Implementierung des Retrieval-Services mit ChromaDB.
    
    Bietet Funktionen für:
    - Semantische Dokumentensuche
    - Dokumentenverwaltung
    - Ähnlichkeitsanalyse
    - Caching häufig verwendeter Dokumente
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        document_processor: DocumentProcessor,
        cache_size: int = 1000
    ):
        """
        Initialisiert den Retrieval-Service.
        
        Args:
            embedding_service: Service für Embedding-Generierung
            document_processor: Service für Dokumentenverarbeitung
            cache_size: Größe des Dokument-Caches
        """
        self.embedding_service = embedding_service
        self.document_processor = document_processor
        self.db = ChromaDBManager()
        self._document_cache = {}
        self._cache_lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert den Retrieval-Service und seine Abhängigkeiten.
        
        Raises:
            RetrievalServiceError: Bei Initialisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "retrieval_initialization"):
                await self.embedding_service.initialize()
                await self.document_processor.initialize()
                await self.db.initialize()
            
            self.logger.info("Retrieval-Service initialisiert")
            
        except Exception as e:
            log_error_with_context(
                self.logger,
                e,
                {},
                "Fehler bei Retrieval-Service-Initialisierung"
            )
            raise RetrievalServiceError(f"Initialisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Service-Ressourcen."""
        try:
            with log_execution_time(self.logger, "service_cleanup"):
                await self.embedding_service.cleanup()
                await self.document_processor.cleanup()
                await self.db.cleanup()
                self._document_cache.clear()
            
            self.logger.info("Retrieval-Service-Ressourcen bereinigt")
            
        except Exception as e:
            self.logger.error(f"Fehler bei Ressourcenbereinigung: {str(e)}")
    
    @lru_cache(maxsize=100)
    def _get_cached_document(self, document_id: str) -> Optional[Document]:
        """
        Ruft ein Dokument aus dem Cache ab.
        
        Args:
            document_id: ID des gewünschten Dokuments
            
        Returns:
            Gecachtes Dokument oder None wenn nicht gefunden
        """
        if doc := self._document_cache.get(document_id):
            self.logger.debug(
                "Cache-Treffer",
                extra={"document_id": document_id}
            )
            return doc
            
        self.logger.debug(
            "Cache-Miss",
            extra={"document_id": document_id}
        )
        return None
    
    @log_function_call(logger)
    async def get_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        Findet ähnliche Dokumente zu einem gegebenen Dokument.
        
        Args:
            document_id: ID des Referenzdokuments
            limit: Maximale Anzahl zurückzugebender Dokumente
            score_threshold: Optionaler Ähnlichkeitsschwellenwert
            
        Returns:
            Liste ähnlicher Dokumente
        
        Raises:
            RetrievalServiceError: Bei Suchfehlern
        """
        try:
            with log_execution_time(self.logger, "similar_documents_search"):
                document = await self.get_document(document_id)
                if not document:
                    self.logger.warning(
                        "Referenzdokument nicht gefunden",
                        extra={"document_id": document_id}
                    )
                    return []
                
                # Dokument als Suchanfrage verwenden
                similar_docs = await self.search_documents(
                    query=document.content,
                    limit=limit + 1  # +1 für das Dokument selbst
                )
                
                # Originaldokument aus Ergebnissen entfernen
                filtered_docs = [
                    doc for doc in similar_docs 
                    if doc.id != document_id
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
    
    @log_function_call(logger)
    async def add_document(self, document: Document) -> Document:
        """
        Fügt ein Dokument zum Retrieval-System hinzu.
        
        Args:
            document: Hinzuzufügendes Dokument
            
        Returns:
            Verarbeitetes Dokument
            
        Raises:
            RetrievalServiceError: Bei Fehlern beim Hinzufügen
        """
        try:
            with request_context():
                with log_execution_time(self.logger, "document_addition"):
                    # Dokument verarbeiten und Chunks erstellen
                    chunks = await self.document_processor.process_document(document)
                    chunk_texts = [chunk.content for chunk in chunks]
                    
                    # Embeddings generieren
                    embeddings = await self.embedding_service.get_embeddings(chunk_texts)
                    
                    # In ChromaDB speichern
                    await self.db.add_documents(
                        ids=[chunk.id for chunk in chunks],
                        embeddings=embeddings,
                        documents=chunk_texts,
                        metadatas=[chunk.metadata for chunk in chunks]
                    )
                    
                    # Cache aktualisieren
                    async with self._cache_lock:
                        self._document_cache[document.id] = document
                        for chunk in chunks:
                            self._document_cache[chunk.id] = chunk
                    
                    self.logger.info(
                        "Dokument hinzugefügt",
                        extra={
                            "document_id": document.id,
                            "chunk_count": len(chunks),
                            "total_chars": sum(len(c.content) for c in chunks)
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
        Ruft ein Dokument anhand seiner ID ab.
        
        Args:
            document_id: ID des gewünschten Dokuments
            
        Returns:
            Gefundenes Dokument oder None
            
        Raises:
            RetrievalServiceError: Bei Abruffehlern
        """
        try:
            with log_execution_time(self.logger, "document_retrieval"):
                # Cache-Check
                cached_doc = self._get_cached_document(document_id)
                if cached_doc:
                    return cached_doc
                
                # Datenbankabfrage
                results = await self.db.query(
                    query_embeddings=[],  # Leer für Metadaten-Abfrage
                    where={"original_id": document_id}
                )
                
                if not results or not results.get("documents"):
                    self.logger.warning(
                        "Dokument nicht gefunden",
                        extra={"document_id": document_id}
                    )
                    return None
                
                # Dokument rekonstruieren
                document = await self._reconstruct_document(results, document_id)
                
                # Cache aktualisieren
                async with self._cache_lock:
                    self._document_cache[document_id] = document
                
                self.logger.info(
                    "Dokument abgerufen",
                    extra={
                        "document_id": document_id,
                        "content_length": len(document.content)
                    }
                )
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
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Sucht nach Dokumenten basierend auf semantischer Ähnlichkeit.
    
        Diese Methode führt eine semantische Suche in der Dokumentensammlung durch. Sie:
        1. Prüft zunächst die verfügbare Dokumentenanzahl
        2. Passt das Limit entsprechend an
        3. Generiert Embeddings für die Suchanfrage
        4. Führt die Ähnlichkeitssuche durch
        5. Verarbeitet und gibt die Ergebnisse zurück
    
        Args:
            query: Suchanfrage als Text
            limit: Maximale Anzahl zurückzugebender Dokumente (Standard: 5)
            metadata_filter: Optionaler Filter für Dokument-Metadaten
            
        Returns:
            Liste gefundener Dokumente, sortiert nach Relevanz
            
        Raises:
            RetrievalServiceError: Bei Fehlern während der Suche oder Verarbeitung
        """
        try:
            with request_context():
                with log_execution_time(self.logger, "document_search"):
                    # Collection-Größe prüfen und Limit anpassen
                    collection_size = self.collection.count()
                    if collection_size == 0:
                        self.logger.warning(
                            "Suche in leerer Collection",
                            extra={"query": query[:100]}  # Erste 100 Zeichen für Logging
                        )
                        return []
                
                    adjusted_limit = min(limit, collection_size)
                    if adjusted_limit < limit:
                        self.logger.info(
                            "Limit an verfügbare Dokumente angepasst",
                            extra={
                                "requested_limit": limit,
                                "collection_size": collection_size,
                                "adjusted_limit": adjusted_limit
                            }
                        )
                
                    # Embedding für Suchanfrage generieren
                    query_embedding = await self.embedding_service.get_embedding(query)

                    # Suche durchführen
                    results = await self.db.query(
                        query_embeddings=[query_embedding],
                        n_results=adjusted_limit,
                        where=metadata_filter
                    )
                
                    # Ergebnisse prüfen
                    if not results or not results.get("documents"):
                        self.logger.info(
                            "Keine relevanten Dokumente gefunden",
                            extra={
                                "query_length": len(query),
                                "has_filter": bool(metadata_filter)
                            }
                        )
                        return []
                
                    # Ergebnisse verarbeiten
                    documents = await self._process_search_results(results)
                
                    self.logger.info(
                        "Dokumente erfolgreich gefunden",
                        extra={
                            "query_length": len(query),
                            "results_count": len(documents),
                            "original_limit": limit,
                            "adjusted_limit": adjusted_limit
                        }
                    )
                    return documents
            
        except Exception as e:
            error_context = {
                "query_length": len(query),
                "requested_limit": limit,
                "has_filter": bool(metadata_filter)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei der Dokumentensuche"
            )
            raise RetrievalServiceError(
                f"Dokumentensuche fehlgeschlagen: {str(e)}"
            )
    
    @log_function_call(logger)
    async def delete_document(self, document_id: str) -> bool:
        """
        Löscht ein Dokument aus dem Retrieval-System.
        
        Args:
            document_id: ID des zu löschenden Dokuments
            
        Returns:
            True wenn erfolgreich gelöscht
            
        Raises:
            RetrievalServiceError: Bei Löschfehlern
        """
        try:
            with log_execution_time(self.logger, "document_deletion"):
                document = await self.get_document(document_id)
                if not document:
                    self.logger.warning(
                        "Zu löschendes Dokument nicht gefunden",
                        extra={"document_id": document_id}
                    )
                    return False
                
                # Chunks löschen
                chunk_ids = [
                    f"{document_id}_chunk_{i}"
                    for i in range(document.metadata.get("total_chunks", 1))
                ]
                await self.db.delete(chunk_ids)
                
                # Cache bereinigen
                async with self._cache_lock:
                    self._document_cache.pop(document_id, None)
                    for chunk_id in chunk_ids:
                        self._document_cache.pop(chunk_id, None)
                
                self.logger.info(
                    "Dokument gelöscht",
                    extra={
                        "document_id": document_id,
                        "chunks_deleted": len(chunk_ids)
                    }
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
            raise RetrievalServiceError(f"Dokument konnte nicht gelöscht werden: {str(e)}")
    
    @log_function_call(logger)
    async def update_document(
        self,
        document_id: str,
        document: Document
    ) -> Optional[Document]:
        """
        Aktualisiert ein bestehendes Dokument.
        
        Args:
            document_id: ID des zu aktualisierenden Dokuments
            document: Neues Dokument
            
        Returns:
            Aktualisiertes Dokument oder None bei Fehler
            
        Raises:
            RetrievalServiceError: Bei Aktualisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "document_update"):
                await self.delete_document(document_id)
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
            raise RetrievalServiceError(
                f"Dokument konnte nicht aktualisiert werden: {str(e)}"
            )
    
    async def _reconstruct_document(
        self,
        results: Dict[str, Any],
        document_id: str
    ) -> Document:
        """
        Hilfsmethode zur Rekonstruktion eines Dokuments aus Chunks.
        
        Args:
            results: Suchergebnisse aus der Datenbank
            document_id: ID des zu rekonstruierenden Dokuments
            
        Returns:
            Rekonstruiertes Dokument
        """
        try:
            with log_execution_time(self.logger, "document_reconstruction"):
                chunks = []
                for i, (doc_id, content, metadata) in enumerate(zip(
                    results["ids"],
                    results["documents"],
                    results["metadatas"]
                )):
                    chunk = Document(
                        id=doc_id,
                        content=content,
                        metadata=metadata,
                        created_at=metadata.get("created_at")
                    )
                    chunks.append(chunk)
                
                # Chunks sortieren und kombinieren
                chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
                combined_content = " ".join(chunk.content for chunk in chunks)
                
                # Dokument erstellen
                metadata = chunks[0].metadata.copy()
                metadata.pop("chunk_index", None)
                metadata.pop("total_chunks", None)
                
                self.logger.debug(
                    "Dokument rekonstruiert",
                    extra={
                        "document_id": document_id,
                        "chunk_count": len(chunks)
                    }
                )
                
                return Document(
                    id=document_id,
                    content=combined_content,
                    metadata=metadata,
                    created_at=chunks[0].created_at
                )
                
        except Exception as e:
            self.logger.error(
                "Fehler bei Dokumentrekonstruktion",
                extra={
                    "document_id": document_id,
                    "error": str(e)
                }
            )
            raise
    
    async def _process_search_results(
        self,
        results: Dict[str, Any]
    ) -> List[Document]:
        """
        Hilfsmethode zur Verarbeitung von Suchergebnissen.
        
        Args:
            results: Rohe Suchergebnisse aus der Datenbank
            
        Returns:
            Liste verarbeiteter Dokumente
        """
        try:
            with log_execution_time(self.logger, "result_processing"):
                documents = []
                for i, (doc_id, content, metadata) in enumerate(zip(
                    results["ids"],
                    results["documents"],
                    results["metadatas"]
                )):
                    original_id = metadata.get("original_id", doc_id)
                    if original_id != doc_id:
                        doc = await self.get_document(original_id)
                        if doc:
                            documents.append(doc)
                    else:
                        doc = Document(
                            id=doc_id,
                            content=content,
                            metadata=metadata,
                            created_at=metadata.get("created_at")
                        )
                        documents.append(doc)
                
                self.logger.debug(
                    "Suchergebnisse verarbeitet",
                    extra={"document_count": len(documents)}
                )
                return documents
                
        except Exception as e:
            self.logger.error(
                "Fehler bei Ergebnisverarbeitung",
                extra={"error": str(e)}
            )
            raise