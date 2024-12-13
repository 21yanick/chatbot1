"""
Document Factory Modul.
Verantwortlich für die konsistente Erstellung und Rekonstruktion von Dokumenten.
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
from src.backend.models.document import Document, DocumentType, DocumentStatus
from src.backend.interfaces.base import ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class DocumentFactoryError(ServiceError):
    """Spezifische Exception für Fehler in der Document Factory."""
    pass

class DocumentFactory:
    """
    Factory-Klasse für die konsistente Erstellung und Rekonstruktion von Dokumenten.
    
    Verantwortlich für:
    - Validierung von Dokumentdaten
    - Erstellung neuer Dokumente
    - Rekonstruktion von Dokumenten aus Chunks
    - Konvertierung zwischen verschiedenen Dokumentformaten
    """
    
    def __init__(self):
        """Initialisiert die Document Factory."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @log_function_call(logger)
    def create_document(
        self,
        id: str,
        title: str,
        content: str,
        source_link: str,
        document_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Document:
        """
        Erstellt ein neues Dokument mit Validierung.
        
        Args:
            id: Dokument-ID
            title: Dokumenttitel
            content: Dokumentinhalt
            source_link: Link zur Quelle
            document_type: Typ des Dokuments
            metadata: Optionale Metadaten
            **kwargs: Weitere optionale Dokumentattribute
            
        Returns:
            Erstelltes Document-Objekt
            
        Raises:
            DocumentFactoryError: Bei ungültigen Dokumentdaten
        """
        try:
            # Basis-Metadaten
            base_metadata = {
                "created_at": datetime.utcnow().isoformat(),
                "processor_version": "1.0",
            }
            
            # Metadaten zusammenführen
            if metadata:
                base_metadata.update(metadata)
                
            # Dokumenttyp validieren
            try:
                doc_type = DocumentType(document_type.lower())
            except ValueError:
                doc_type = DocumentType.SONSTIGES
                self.logger.warning(
                    f"Ungültiger Dokumenttyp, verwende SONSTIGES",
                    extra={"provided_type": document_type}
                )
            
            # Dokument erstellen
            document = Document(
                id=id,
                title=title,
                content=content,
                source_link=source_link,
                document_type=doc_type,
                status=DocumentStatus.PENDING,
                metadata=base_metadata,
                **kwargs
            )
            
            self.logger.info(
                "Dokument erfolgreich erstellt",
                extra={
                    "document_id": id,
                    "type": doc_type.value,
                    "metadata_keys": list(base_metadata.keys())
                }
            )
            
            return document
            
        except Exception as e:
            error_context = {
                "document_id": id,
                "title": title,
                "type": document_type
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumenterstellung"
            )
            raise DocumentFactoryError(f"Dokumenterstellung fehlgeschlagen: {str(e)}")

    @log_function_call(logger)
    def create_chunk(
        self,
        original_doc: Document,
        chunk_content: str,
        chunk_index: int,
        total_chunks: int,
        section: Optional[str] = None
    ) -> Document:
        """
        Erstellt einen Dokumentchunk aus einem Originaldokument.
        
        Args:
            original_doc: Originaldokument
            chunk_content: Inhalt des Chunks
            chunk_index: Index des Chunks
            total_chunks: Gesamtanzahl der Chunks
            section: Optionale Abschnittsreferenz
            
        Returns:
            Erstellter Dokumentchunk
        """
        try:
            # Chunk-Metadaten erstellen
            chunk_metadata = {
                "original_id": original_doc.id,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "section": section
            }
            
            # Originale Metadaten übernehmen und mit Chunk-Metadaten ergänzen
            if original_doc.metadata:
                chunk_metadata.update(original_doc.metadata)
            
            # Chunk erstellen
            chunk = Document(
                id=f"{original_doc.id}_chunk_{chunk_index}",
                title=f"{original_doc.title} (Chunk {chunk_index + 1}/{total_chunks})",
                content=chunk_content,
                source_link=original_doc.source_link,
                document_type=original_doc.document_type,
                status=original_doc.status,
                metadata=chunk_metadata,
                created_at=original_doc.created_at,
                language=original_doc.language,
                topics=original_doc.topics.copy() if original_doc.topics else []
            )
            
            self.logger.debug(
                "Chunk erstellt",
                extra={
                    "original_id": original_doc.id,
                    "chunk_index": chunk_index,
                    "chunk_length": len(chunk_content)
                }
            )
            
            return chunk
            
        except Exception as e:
            error_context = {
                "original_id": original_doc.id,
                "chunk_index": chunk_index
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Chunk-Erstellung"
            )
            raise DocumentFactoryError(f"Chunk-Erstellung fehlgeschlagen: {str(e)}")

    @log_function_call(logger)
    def reconstruct_from_chunks(self, chunks: List[Document], document_id: str) -> Document:
        """
        Rekonstruiert ein Dokument aus seinen Chunks.
        
        Args:
            chunks: Liste der Dokumentchunks
            document_id: ID des zu rekonstruierenden Dokuments
            
        Returns:
            Rekonstruiertes Dokument
            
        Raises:
            DocumentFactoryError: Bei Fehlern in der Rekonstruktion
        """
        try:
            if not chunks:
                raise DocumentFactoryError("Keine Chunks für Rekonstruktion vorhanden")
                
            # Chunks nach Index sortieren
            chunks.sort(key=lambda x: x.metadata.get("chunk_index", 0))
            
            # Basis-Metadaten vom ersten Chunk
            base_chunk = chunks[0]
            base_metadata = base_chunk.metadata.copy()
            
            # Chunk-spezifische Metadaten entfernen
            chunk_metadata_keys = ["chunk_index", "total_chunks", "original_id"]
            for key in chunk_metadata_keys:
                base_metadata.pop(key, None)
            
            # Inhalte zusammenführen
            combined_content = " ".join(chunk.content for chunk in chunks)
            
            # Dokument rekonstruieren
            document = Document(
                id=document_id,
                title=base_chunk.title.split(" (Chunk")[0],  # Original-Titel wiederherstellen
                content=combined_content,
                source_link=base_chunk.source_link,
                document_type=base_chunk.document_type,
                metadata=base_metadata,
                created_at=base_chunk.created_at,
                language=base_chunk.language,
                topics=base_chunk.topics,
                status=base_chunk.status
            )
            
            self.logger.info(
                "Dokument erfolgreich rekonstruiert",
                extra={
                    "document_id": document_id,
                    "chunk_count": len(chunks),
                    "total_length": len(combined_content)
                }
            )
            
            return document
            
        except Exception as e:
            error_context = {
                "document_id": document_id,
                "chunk_count": len(chunks)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumentrekonstruktion"
            )
            raise DocumentFactoryError(f"Dokumentrekonstruktion fehlgeschlagen: {str(e)}")

    @log_function_call(logger)
    def create_from_database_result(self, result: Dict[str, Any]) -> Document:
        """
        Erstellt ein Dokument aus einem Datenbankergebnis.
        
        Args:
            result: Datenbankergebnis (ChromaDB-Format)
            
        Returns:
            Erstelltes Dokument
        """
        try:
            if not result or "ids" not in result:
                raise DocumentFactoryError("Ungültiges Datenbankergebnis")
            
            # Metadaten extrahieren und validieren
            metadata = result.get("metadatas", [{}])[0] or {}
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Pflichtfelder mit Fallbacks
            doc_id = result["ids"][0]
            content = result.get("documents", [""])[0] or ""
            
            # Dokument erstellen
            document = Document(
                id=doc_id,
                title=metadata.get("title", f"Dokument {doc_id[:8]}"),
                content=content,
                source_link=metadata.get("source_link", f"https://default-source/{doc_id}"),
                document_type=DocumentType(metadata.get("document_type", "sonstiges")),
                metadata=metadata,
                created_at=datetime.fromisoformat(metadata.get("created_at", datetime.utcnow().isoformat())),
                language=metadata.get("language", "de"),
                topics=metadata.get("topics", []),
                status=DocumentStatus(metadata.get("status", "pending"))
            )
            
            self.logger.debug(
                "Dokument aus Datenbankergebnis erstellt",
                extra={
                    "document_id": doc_id,
                    "has_metadata": bool(metadata)
                }
            )
            
            return document
            
        except Exception as e:
            error_context = {
                "result_keys": list(result.keys()) if result else None
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumenterstellung aus Datenbankergebnis"
            )
            raise DocumentFactoryError(
                f"Erstellung aus Datenbankergebnis fehlgeschlagen: {str(e)}"
            )