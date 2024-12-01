"""
Dokument-Modell-Modul.
Definiert das Datenmodell für Dokumente im System.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

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

class Document(BaseModel):
    """
    Basis-Dokumentenmodell für Inhalt und Metadaten.
    
    Repräsentiert ein einzelnes Dokument im System mit seinem Inhalt,
    Metadaten und zugehörigen Zeitstempeln.
    """
    
    id: str = Field(
        ..., 
        description="Eindeutige Dokument-ID"
    )
    content: str = Field(
        ..., 
        description="Hauptinhalt des Dokuments"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Zusätzliche Dokument-Metadaten"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Erstellungszeitpunkt des Dokuments"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Zeitpunkt der letzten Aktualisierung"
    )
    source: Optional[str] = Field(
        default=None,
        description="Quelle des Dokuments"
    )
    
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
                "content": self.content,
                "metadata": {
                    **self.metadata,
                    "created_at": self.created_at.isoformat(),
                    "updated_at": self.updated_at.isoformat() if self.updated_at else None,
                    "source": self.source
                }
            }
            
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
            f"Document {self.id} "
            f"(Quelle: {self.source or 'Unbekannt'}, "
            f"Länge: {len(self.content)} Zeichen)"
        )
    
    class Config:
        """Pydantic Modell-Konfiguration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        
        # Zusätzliche Validierung
        validate_assignment = True  # Validierung bei Attribut-Zuweisung
        extra = "forbid"  # Keine zusätzlichen Felder erlaubt