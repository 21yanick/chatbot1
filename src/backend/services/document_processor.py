"""
Dokument-Verarbeitungs-Modul.
Verantwortlich für die Analyse, Aufbereitung und Chunking von Dokumenten.
"""

from typing import List, Dict, Any, Optional
import re
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..models.document import Document
from ..interfaces.base import BaseService, ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class DocumentProcessorError(ServiceError):
    """Spezifische Exception für Fehler bei der Dokumentenverarbeitung."""
    pass

class DocumentProcessor(BaseService):
    """
    Service für die Verarbeitung und Chunking von Dokumenten.
    
    Verantwortlich für:
    - Textbereinigung und Normalisierung
    - Dokumenten-Chunking
    - Metadaten-Extraktion
    - Spracherkennung und Themenextraktion
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        """
        Initialisiert den Dokumenten-Prozessor.
        
        Args:
            chunk_size: Maximale Größe eines Chunks in Zeichen
            chunk_overlap: Überlappung zwischen Chunks in Zeichen
            min_chunk_size: Minimale Chunk-Größe für gültige Dokumente
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self._splitter = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert den Dokumenten-Prozessor.
        
        Raises:
            DocumentProcessorError: Bei Initialisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "init_text_splitter"):
                self._splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                    is_separator_regex=r'\n\n|\n|\. |\?|\!'
                )
            
            self.logger.info(
                "Dokumenten-Prozessor initialisiert",
                extra={
                    "chunk_size": self.chunk_size,
                    "overlap": self.chunk_overlap,
                    "min_size": self.min_chunk_size
                }
            )
            
        except Exception as e:
            error_context = {
                "chunk_size": self.chunk_size,
                "overlap": self.chunk_overlap
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumenten-Prozessor-Initialisierung"
            )
            raise DocumentProcessorError(f"Initialisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Prozessor-Ressourcen."""
        self._splitter = None
        self.logger.info("Dokumenten-Prozessor-Ressourcen bereinigt")
    
    def _clean_text(self, text: str) -> str:
        """
        Bereinigt und normalisiert Textinhalt.
        
        Args:
            text: Zu bereinigender Text
            
        Returns:
            Bereinigter Text
        """
        try:
            with log_execution_time(self.logger, "text_cleaning"):
                # Übermäßige Whitespaces entfernen
                text = re.sub(r'\s+', ' ', text)
                # Spezielle Zeichen entfernen, Grundzeichensetzung beibehalten
                text = re.sub(r'[^\w\s.,!?-]', '', text)
                cleaned_text = text.strip()
                
                self.logger.debug(
                    "Text bereinigt",
                    extra={
                        "original_length": len(text),
                        "cleaned_length": len(cleaned_text)
                    }
                )
                return cleaned_text
                
        except Exception as e:
            self.logger.error(f"Fehler bei Textbereinigung: {str(e)}")
            return text  # Ursprünglichen Text bei Fehler zurückgeben
    
    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extrahiert Metadaten aus dem Dokumenteninhalt.
        
        Args:
            content: Dokumenteninhalt
            
        Returns:
            Dictionary mit extrahierten Metadaten
        """
        try:
            with log_execution_time(self.logger, "metadata_extraction"):
                metadata = {
                    "length": len(content),
                    "processed_at": datetime.utcnow().isoformat(),
                    "language": self._detect_language(content),
                    "topics": self._extract_topics(content)
                }
                
                self.logger.debug(
                    "Metadaten extrahiert",
                    extra={
                        "metadata_keys": list(metadata.keys()),
                        "detected_language": metadata["language"]
                    }
                )
                return metadata
                
        except Exception as e:
            self.logger.error(f"Fehler bei Metadaten-Extraktion: {str(e)}")
            return {
                "length": len(content),
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def _detect_language(self, content: str) -> str:
        """
        Einfache Spracherkennung.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Erkannter Sprachcode ("de" oder "en")
        """
        try:
            # Vereinfachte Implementierung
            # In Produktion sollte eine richtige Spracherkennungsbibliothek verwendet werden
            german_indicators = ["der", "die", "das", "und", "ist", "sind", "werden"]
            text_lower = content.lower()
            german_word_count = sum(1 for word in german_indicators if word in text_lower)
            
            is_german = german_word_count >= 2
            
            self.logger.debug(
                "Sprache erkannt",
                extra={
                    "detected": "de" if is_german else "en",
                    "confidence_indicators": german_word_count
                }
            )
            
            return "de" if is_german else "en"
            
        except Exception as e:
            self.logger.error(f"Fehler bei Spracherkennung: {str(e)}")
            return "unknown"
    
    def _extract_topics(self, content: str) -> List[str]:
        """
        Extrahiert Hauptthemen aus dem Inhalt.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Liste erkannter Themen
        """
        try:
            # Vereinfachte Implementierung
            # In Produktion sollte richtiges Topic Modeling verwendet werden
            common_vehicle_topics = {
                "sicherheit": ["sicherheit", "schutz", "airbag", "gurt"],
                "parken": ["parken", "parkplatz", "garage", "einparken"],
                "elektro": ["elektro", "batterie", "laden", "reichweite"],
                "antrieb": ["antrieb", "motor", "getriebe", "leistung"],
                "wartung": ["wartung", "service", "inspektion", "reparatur"],
                "reifen": ["reifen", "profil", "luftdruck", "wechsel"],
                "bremsen": ["bremse", "bremsbelag", "abs", "bremssystem"],
                "beleuchtung": ["licht", "scheinwerfer", "led", "blinker"],
                "fahrassistenz": ["assistenz", "tempomat", "spurhalte", "sensor"]
            }
            
            content_lower = content.lower()
            found_topics = []
            
            for topic, keywords in common_vehicle_topics.items():
                if any(keyword in content_lower for keyword in keywords):
                    found_topics.append(topic)
            
            self.logger.debug(
                "Themen extrahiert",
                extra={
                    "found_topics_count": len(found_topics),
                    "topics": found_topics
                }
            )
            
            return found_topics
            
        except Exception as e:
            self.logger.error(f"Fehler bei Themenextraktion: {str(e)}")
            return []
    
    @log_function_call(logger)
    async def process_document(
        self,
        document: Document,
        update_metadata: bool = True
    ) -> List[Document]:
        """
        Verarbeitet ein Dokument und teilt es in Chunks.
        
        Args:
            document: Zu verarbeitendes Dokument
            update_metadata: Ob Metadaten aktualisiert werden sollen
            
        Returns:
            Liste der verarbeiteten Dokument-Chunks
            
        Raises:
            DocumentProcessorError: Bei Verarbeitungsfehlern
        """
        if not self._splitter:
            raise DocumentProcessorError("Dokumenten-Prozessor nicht initialisiert")
        
        try:
            with request_context():
                with log_execution_time(self.logger, "document_processing"):
                    # Inhalt bereinigen
                    cleaned_content = self._clean_text(document.content)
                    
                    # In Chunks aufteilen
                    chunks = self._splitter.split_text(cleaned_content)
                    
                    # Zu kleine Chunks filtern
                    chunks = [
                        chunk for chunk in chunks 
                        if len(chunk) >= self.min_chunk_size
                    ]
                    
                    # Dokument-Chunks erstellen
                    doc_chunks = []
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = {
                            "original_id": document.id,
                            "chunk_index": i,
                            "total_chunks": len(chunks)
                        }
                        
                        if update_metadata:
                            chunk_metadata.update(self._extract_metadata(chunk))
                        
                        if document.metadata:
                            chunk_metadata.update(document.metadata)
                        
                        doc_chunks.append(Document(
                            id=f"{document.id}_chunk_{i}",
                            content=chunk,
                            metadata=chunk_metadata,
                            source=document.source,
                            created_at=document.created_at
                        ))
                    
                    self.logger.info(
                        f"Dokument verarbeitet",
                        extra={
                            "document_id": document.id,
                            "chunks_created": len(doc_chunks),
                            "original_length": len(document.content),
                            "processed_length": sum(len(c.content) for c in doc_chunks)
                        }
                    )
                    return doc_chunks
            
        except Exception as e:
            error_context = {
                "document_id": document.id,
                "content_length": len(document.content)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumentenverarbeitung"
            )
            raise DocumentProcessorError(
                f"Dokument {document.id} konnte nicht verarbeitet werden: {str(e)}"
            )
    
    @log_function_call(logger)
    async def validate_document(self, document: Document) -> bool:
        """
        Validiert Dokumenteninhalt und -struktur.
        
        Args:
            document: Zu validierendes Dokument
            
        Returns:
            True wenn Dokument gültig, False sonst
        """
        try:
            with log_execution_time(self.logger, "document_validation"):
                if not document.content or len(document.content.strip()) < self.min_chunk_size:
                    self.logger.warning(
                        f"Dokumentinhalt zu kurz",
                        extra={
                            "document_id": document.id,
                            "content_length": len(document.content or "")
                        }
                    )
                    return False
                
                if len(document.content) > 1_000_000:  # 1MB Limit
                    self.logger.warning(
                        f"Dokumentinhalt zu groß",
                        extra={
                            "document_id": document.id,
                            "content_length": len(document.content)
                        }
                    )
                    return False
                
                self.logger.debug(
                    f"Dokument validiert",
                    extra={
                        "document_id": document.id,
                        "is_valid": True
                    }
                )
                return True
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei Dokumentvalidierung: {str(e)}",
                extra={"document_id": document.id}
            )
            return False