"""
Dokument-Modell-Modul.
Definiert das Datenmodell für Dokumente im System.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum

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

class DocumentType(str, Enum):
    """Enum für verschiedene Dokumenttypen."""
    GESETZ = "gesetz"
    VERORDNUNG = "verordnung"
    RICHTLINIE = "richtlinie"
    ANLEITUNG = "anleitung"
    HANDBUCH = "handbuch"
    ARTIKEL = "artikel"
    SONSTIGES = "sonstiges"

class DocumentStatus(str, Enum):
    """Enum für Dokumentstatus."""
    PENDING = "pending"         # Warten auf Verarbeitung
    PROCESSING = "processing"   # Wird verarbeitet
    COMPLETED = "completed"     # Verarbeitung abgeschlossen
    FAILED = "failed"          # Verarbeitung fehlgeschlagen
    ARCHIVED = "archived"      # Archiviert

class ChunkMetadata(BaseModel):
    """Metadaten für einen einzelnen Dokument-Chunk."""
    chunk_index: int = Field(..., description="Position des Chunks im Originaldokument")
    total_chunks: int = Field(..., description="Gesamtanzahl der Chunks im Dokument")
    chunk_type: str = Field("paragraph", description="Art des Chunks (z.B. paragraph, section)")
    section: Optional[str] = Field(None, description="Abschnitt/Paragraph Referenz")
    start_char: int = Field(..., description="Startposition im Originaldokument")
    end_char: int = Field(..., description="Endposition im Originaldokument")

class Document(BaseModel):
    """
    Basis-Dokumentenmodell für Inhalt und Metadaten.
    
    Repräsentiert ein einzelnes Dokument im System mit seinem Inhalt,
    Metadaten und zugehörigen Zeitstempeln.
    """
    
    # Basis-Felder
    id: str = Field(
        ..., 
        description="Eindeutige Dokument-ID"
    )
    title: str = Field(
        ...,
        description="Titel des Dokuments",
        min_length=3
    )
    content: str = Field(
        ..., 
        description="Hauptinhalt des Dokuments"
    )
    
    # Pflichtmetadaten
    source_link: str = Field(
        ...,
        description="Link zum Originaldokument (zwingend erforderlich)"
    )
    document_type: DocumentType = Field(
        ...,
        description="Typ des Dokuments"
    )
    
    # Status und Tracking
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING,
        description="Aktueller Status des Dokuments"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Erstellungszeitpunkt des Dokuments"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Zeitpunkt der letzten Aktualisierung"
    )
    last_validated: Optional[datetime] = Field(
        default=None,
        description="Zeitpunkt der letzten Validierung"
    )
    
    # Kategorisierung
    category: Optional[str] = Field(
        default=None,
        description="Hauptkategorie des Dokuments"
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Liste der Themen/Tags"
    )
    language: str = Field(
        default="de",
        description="Sprache des Dokuments (ISO 639-1)"
    )
    
    # Chunking
    chunk_metadata: Optional[ChunkMetadata] = Field(
        default=None,
        description="Metadaten für Dokument-Chunks"
    )
    original_doc_id: Optional[str] = Field(
        default=None,
        description="ID des Originaldokuments falls dies ein Chunk ist"
    )
    
    # Beziehungen
    related_docs: List[str] = Field(
        default_factory=list,
        description="IDs verwandter Dokumente"
    )
    prerequisites: List[str] = Field(
        default_factory=list,
        description="IDs vorausgesetzter Dokumente"
    )
    supersedes: List[str] = Field(
        default_factory=list,
        description="IDs von Dokumenten die dieses ersetzt"
    )
    
    # Ranking und Statistiken
    importance_score: float = Field(
        default=1.0,
        description="Wichtigkeits-Score des Dokuments",
        ge=0.0,
        le=1.0
    )
    validation_score: float = Field(
        default=1.0,
        description="Validierungs-Score",
        ge=0.0,
        le=1.0
    )
    usage_count: int = Field(
        default=0,
        description="Nutzungszähler"
    )
    
    # Zusätzliche Metadaten
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Zusätzliche Dokument-Metadaten"
    )
    
    @validator('source_link')
    def validate_source_link(cls, v):
        """Validiert den Source-Link."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('source_link muss eine gültige HTTP(S) URL sein')
        return v
    
    @log_function_call(logger)
    def update_content(self, new_content: str) -> None:
        """
        Aktualisiert den Dokumentinhalt.
        
        Args:
            new_content: Neuer Dokumentinhalt
            
        Note:
            Aktualisiert automatisch den updated_at Zeitstempel.
        """
        try:
            old_length = len(self.content)
            self.content = new_content
            self.updated_at = datetime.utcnow()
            
            logger.debug(
                "Dokumentinhalt aktualisiert",
                extra={
                    "document_id": self.id,
                    "old_length": old_length,
                    "new_length": len(new_content)
                }
            )
            
        except Exception as e:
            logger.error(
                "Fehler bei Inhalts-Aktualisierung",
                extra={
                    "document_id": self.id,
                    "error": str(e)
                }
            )
            raise
    
    @log_function_call(logger)
    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Aktualisiert die Dokument-Metadaten.
        
        Args:
            metadata: Neue oder zu aktualisierende Metadaten
            
        Note:
            - Führt ein Update der bestehenden Metadaten durch
            - Aktualisiert automatisch den updated_at Zeitstempel
        """
        try:
            old_keys = set(self.metadata.keys())
            self.metadata.update(metadata)
            new_keys = set(self.metadata.keys())
            self.updated_at = datetime.utcnow()
            
            logger.debug(
                "Metadaten aktualisiert",
                extra={
                    "document_id": self.id,
                    "added_keys": list(new_keys - old_keys),
                    "updated_keys": list(old_keys & new_keys),
                    "total_keys": len(self.metadata)
                }
            )
            
        except Exception as e:
            logger.error(
                "Fehler bei Metadaten-Aktualisierung",
                extra={
                    "document_id": self.id,
                    "error": str(e)
                }
            )
            raise

    @log_function_call(logger)
    def increment_usage(self) -> None:
        """Erhöht den Nutzungszähler des Dokuments."""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()
        logger.debug(f"Nutzungszähler erhöht für Dokument {self.id}: {self.usage_count}")

    @log_function_call(logger)
    def to_embedding_format(self) -> Dict[str, Any]:
        """
        Konvertiert das Dokument in ein Format für Embedding-Speicherung.
        
        Returns:
            Dictionary mit Dokumentdaten im Embedding-Format
            
        Note:
            Bereitet das Dokument für die Speicherung in der Vektordatenbank vor,
            einschließlich aller relevanten Metadaten und Zeitstempel.
        """
        try:
            formatted_doc = {
                "id": self.id,
                "title": self.title,
                "content": self.content,
                "metadata": {
                    "source_link": self.source_link,
                    "document_type": self.document_type.value,
                    "status": self.status.value,
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                    "category": self.category,
                    "topics": self.topics,
                    "language": self.language,
                    "importance_score": self.importance_score,
                    "validation_score": self.validation_score,
                    "usage_count": self.usage_count,
                    **self.metadata
                }
            }
            
            # Chunk-spezifische Metadaten hinzufügen falls vorhanden
            if self.chunk_metadata:
                formatted_doc["metadata"].update({
                    "chunk_index": self.chunk_metadata.chunk_index,
                    "total_chunks": self.chunk_metadata.total_chunks,
                    "chunk_type": self.chunk_metadata.chunk_type,
                    "section": self.chunk_metadata.section,
                    "original_doc_id": self.original_doc_id
                })
            
            logger.debug(
                "Dokument zu Embedding-Format konvertiert",
                extra={
                    "document_id": self.id,
                    "metadata_keys": list(formatted_doc["metadata"].keys())
                }
            )
            
            return formatted_doc
            
        except Exception as e:
            logger.error(
                "Fehler bei Konvertierung zu Embedding-Format",
                extra={
                    "document_id": self.id,
                    "error": str(e)
                }
            )
            raise
    
    def __str__(self) -> str:
        """String-Repräsentation des Dokuments."""
        return (
            f"Document {self.id} - {self.title} "
            f"(Typ: {self.document_type.value}, "
            f"Status: {self.status.value}, "
            f"Sprache: {self.language})"
        )
    
    class Config:
        """Pydantic Modell-Konfiguration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        
        # Zusätzliche Validierung
        validate_assignment = True  # Validierung bei Attribut-Zuweisung
        extra = "forbid"  # Keine zusätzlichen Felder erlaubt