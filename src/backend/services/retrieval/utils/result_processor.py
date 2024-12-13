"""
Result Processor Modul.
Verantwortlich für die Verarbeitung und Aufbereitung von Suchergebnissen.
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
from .validators import DocumentValidator

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class ResultProcessorError(ServiceError):
    """Spezifische Exception für Fehler bei der Ergebnisverarbeitung."""
    pass

class ResultProcessor:
    """
    Prozessor für Suchergebnisse und Dokumentenkonvertierung.
    
    Features:
    - Verarbeitung von ChromaDB-Suchergebnissen
    - Konvertierung zwischen verschiedenen Dokumentformaten
    - Validierung und Filterung von Ergebnissen
    - Rangfolgenbestimmung und Scoring
    """
    
    def __init__(self, document_validator: Optional[DocumentValidator] = None):
        """
        Initialisiert den Result Processor.
        
        Args:
            document_validator: Optionaler Validator für Dokumente
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.validator = document_validator or DocumentValidator()
        
    @log_function_call(logger)
    async def process_search_results(
        self,
        results: Dict[str, Any],
        include_scores: bool = True,
        min_score: Optional[float] = None
    ) -> List[Document]:
        """
        Verarbeitet Suchergebnisse aus ChromaDB.
        
        Args:
            results: Rohe Suchergebnisse
            include_scores: Ob Ähnlichkeitsscores einbezogen werden sollen
            min_score: Minimaler Score für Ergebnisse
            
        Returns:
            Liste verarbeiteter Dokumente
            
        Raises:
            ResultProcessorError: Bei Verarbeitungsfehlern
        """
        try:
            with log_execution_time(self.logger, "search_result_processing"):
                # Ergebnisstruktur validieren
                if not self._validate_results_structure(results):
                    raise ResultProcessorError("Ungültiges Ergebnisformat")
                
                # Ergebnislisten extrahieren
                documents = []
                for i, (doc_id, content, metadata) in enumerate(zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0]
                )):
                    # Score prüfen falls vorhanden
                    if min_score is not None and include_scores:
                        if (
                            "distances" in results and
                            results["distances"][0][i] > min_score
                        ):
                            continue
                    
                    # Dokument erstellen
                    try:
                        doc = await self._create_document_from_result(
                            doc_id,
                            content,
                            metadata,
                            results.get("distances", [[]])[0][i] if include_scores else None
                        )
                        if doc and await self.validator.validate(doc):
                            documents.append(doc)
                    except Exception as e:
                        self.logger.warning(
                            f"Fehler bei Dokumenterstellung: {str(e)}",
                            extra={"doc_id": doc_id}
                        )
                        continue
                
                self.logger.info(
                    "Suchergebnisse verarbeitet",
                    extra={
                        "total_results": len(results["ids"][0]),
                        "valid_results": len(documents)
                    }
                )
                
                return documents
                
        except Exception as e:
            error_context = {
                "result_keys": list(results.keys()) if results else None
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Ergebnisverarbeitung"
            )
            raise ResultProcessorError(f"Ergebnisverarbeitung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def process_chunk_results(
        self,
        results: Dict[str, Any],
        original_id: str
    ) -> Optional[Document]:
        """
        Verarbeitet Chunk-Ergebnisse zur Dokumentrekonstruktion.
        
        Args:
            results: Chunk-Ergebnisse
            original_id: ID des Originaldokuments
            
        Returns:
            Rekonstruiertes Dokument oder None bei Fehlern
            
        Raises:
            ResultProcessorError: Bei Rekonstruktionsfehlern
        """
        try:
            with log_execution_time(self.logger, "chunk_processing"):
                if not self._validate_results_structure(results):
                    raise ResultProcessorError("Ungültige Chunk-Ergebnisse")
                
                # Chunks nach Index sortieren
                chunks = []
                for i, (doc_id, content, metadata) in enumerate(zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0]
                )):
                    chunks.append({
                        "id": doc_id,
                        "content": content,
                        "metadata": metadata,
                        "index": metadata.get("chunk_index", i)
                    })
                
                chunks.sort(key=lambda x: x["index"])
                
                # Dokumentdaten extrahieren
                base_metadata = chunks[0]["metadata"].copy()
                for key in ["chunk_index", "total_chunks", "original_id"]:
                    base_metadata.pop(key, None)
                
                # Inhalte zusammenführen
                combined_content = " ".join(chunk["content"] for chunk in chunks)
                
                # Dokument erstellen
                document = Document(
                    id=original_id,
                    title=base_metadata.get("title", f"Dokument {original_id[:8]}"),
                    content=combined_content,
                    source_link=base_metadata.get("source_link", f"https://default-source/{original_id}"),
                    document_type=DocumentType(base_metadata.get("document_type", "sonstiges")),
                    status=DocumentStatus(base_metadata.get("status", "completed")),
                    metadata=base_metadata,
                    created_at=datetime.fromisoformat(base_metadata.get(
                        "created_at",
                        datetime.utcnow().isoformat()
                    )),
                    language=base_metadata.get("language", "de"),
                    topics=base_metadata.get("topics", [])
                )
                
                if not await self.validator.validate(document):
                    raise ResultProcessorError("Rekonstruiertes Dokument ungültig")
                
                self.logger.info(
                    "Dokument aus Chunks rekonstruiert",
                    extra={
                        "document_id": original_id,
                        "chunk_count": len(chunks),
                        "total_length": len(combined_content)
                    }
                )
                
                return document
                
        except Exception as e:
            error_context = {
                "original_id": original_id,
                "result_count": len(results.get("ids", [[]])[0]) if results else 0
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Chunk-Verarbeitung"
            )
            raise ResultProcessorError(f"Chunk-Verarbeitung fehlgeschlagen: {str(e)}")
    
    async def _create_document_from_result(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
        score: Optional[float] = None
    ) -> Optional[Document]:
        """
        Erstellt ein Dokument aus einem einzelnen Suchergebnis.
        
        Args:
            doc_id: Dokument-ID
            content: Dokumentinhalt
            metadata: Dokumentmetadaten
            score: Optionaler Ähnlichkeitsscore
            
        Returns:
            Erstelltes Dokument oder None bei Fehlern
        """
        try:
            # Metadaten validieren und standardisieren
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Score hinzufügen falls vorhanden
            if score is not None:
                metadata["search_score"] = score
            
            # Dokument erstellen
            document = Document(
                id=doc_id,
                title=metadata.get("title", f"Dokument {doc_id[:8]}"),
                content=content,
                source_link=metadata.get("source_link", f"https://default-source/{doc_id}"),
                document_type=DocumentType(metadata.get("document_type", "sonstiges")),
                status=DocumentStatus(metadata.get("status", "completed")),
                metadata=metadata,
                created_at=datetime.fromisoformat(metadata.get(
                    "created_at",
                    datetime.utcnow().isoformat()
                )),
                language=metadata.get("language", "de"),
                topics=metadata.get("topics", [])
            )
            
            return document
            
        except Exception as e:
            self.logger.warning(
                f"Fehler bei Dokumenterstellung aus Ergebnis: {str(e)}",
                extra={"doc_id": doc_id}
            )
            return None
    
    def _validate_results_structure(self, results: Dict[str, Any]) -> bool:
        """
        Validiert die Struktur von ChromaDB-Ergebnissen.
        
        Args:
            results: Zu validierende Ergebnisse
            
        Returns:
            True wenn Struktur gültig
        """
        required_keys = ["ids", "documents", "metadatas"]
        if not all(key in results for key in required_keys):
            return False
        
        # Prüfen ob Listen vorhanden und nicht leer
        if not all(isinstance(results[key], list) for key in required_keys):
            return False
        
        # Prüfen ob innere Listen vorhanden
        if not all(isinstance(results[key][0], list) for key in required_keys):
            return False
        
        # Prüfen ob alle Listen gleich lang sind
        lengths = [len(results[key][0]) for key in required_keys]
        if not all(length == lengths[0] for length in lengths):
            return False
        
        return True