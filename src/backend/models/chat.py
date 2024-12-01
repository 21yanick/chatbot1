"""
Chat-Modell-Modul.
Definiert die Datenmodelle für Chat-Sessions und Nachrichten.
"""

from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
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

class Message(BaseModel):
    """
    Modell für eine einzelne Chat-Nachricht.
    
    Repräsentiert eine Nachricht innerhalb einer Chat-Session,
    einschließlich Inhalt, Rolle des Absenders und Metadaten.
    """
    
    content: str = Field(
        ..., 
        description="Nachrichteninhalt"
    )
    role: Literal["user", "assistant", "system"] = Field(
        ..., 
        description="Rolle des Nachrichtenabsenders"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Zeitstempel der Nachricht"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Zusätzliche Nachrichtenmetadaten"
    )
    
    def __str__(self) -> str:
        """String-Repräsentation der Nachricht."""
        return f"{self.role} ({self.timestamp.isoformat()}): {self.content[:50]}..."
    
    class Config:
        """Pydantic Modell-Konfiguration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class ChatSession(BaseModel):
    """
    Modell für eine Chat-Session mit Nachrichtenverlauf.
    
    Verwaltet eine Sammlung von Nachrichten sowie zugehörige
    Metadaten und Kontextinformationen für eine Chat-Konversation.
    """
    
    id: str = Field(
        ..., 
        description="Eindeutige Chat-Session-ID"
    )
    messages: List[Message] = Field(
        default_factory=list,
        description="Liste der Chat-Nachrichten"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Erstellungszeitpunkt der Session"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Zeitpunkt der letzten Nachricht"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Session-Metadaten"
    )
    context_documents: List[str] = Field(
        default_factory=list,
        description="Liste relevanter Dokument-IDs für Kontext"
    )
    
    @log_function_call(logger)
    def add_message(self, message: Message) -> None:
        """
        Fügt eine neue Nachricht zur Chat-Session hinzu.
        
        Args:
            message: Hinzuzufügende Nachricht
            
        Note:
            Aktualisiert automatisch den updated_at Zeitstempel.
        """
        try:
            self.messages.append(message)
            self.updated_at = datetime.utcnow()
            
            logger.debug(
                "Nachricht zur Session hinzugefügt",
                extra={
                    "session_id": self.id,
                    "message_role": message.role,
                    "content_length": len(message.content)
                }
            )
            
        except Exception as e:
            logger.error(
                "Fehler beim Hinzufügen der Nachricht",
                extra={
                    "session_id": self.id,
                    "error": str(e)
                }
            )
            raise
    
    @log_function_call(logger)
    def get_context(self, max_messages: Optional[int] = None) -> List[Message]:
        """
        Ruft den aktuellen Nachrichtenkontext ab.
        
        Args:
            max_messages: Optionale Begrenzung der Nachrichtenanzahl
            
        Returns:
            Liste der Kontext-Nachrichten
        """
        try:
            messages = self.messages[-max_messages:] if max_messages else self.messages
            
            logger.debug(
                "Kontext abgerufen",
                extra={
                    "session_id": self.id,
                    "requested_messages": max_messages,
                    "returned_messages": len(messages)
                }
            )
            
            return messages
            
        except Exception as e:
            logger.error(
                "Fehler beim Abrufen des Kontexts",
                extra={
                    "session_id": self.id,
                    "error": str(e)
                }
            )
            raise
    
    @log_function_call(logger)
    def add_context_document(self, document_id: str) -> None:
        """
        Fügt eine Dokument-ID zum Kontext hinzu.
        
        Args:
            document_id: ID des hinzuzufügenden Kontextdokuments
        """
        try:
            if document_id not in self.context_documents:
                self.context_documents.append(document_id)
                
                logger.debug(
                    "Kontextdokument hinzugefügt",
                    extra={
                        "session_id": self.id,
                        "document_id": document_id
                    }
                )
                
        except Exception as e:
            logger.error(
                "Fehler beim Hinzufügen des Kontextdokuments",
                extra={
                    "session_id": self.id,
                    "document_id": document_id,
                    "error": str(e)
                }
            )
            raise
    
    @log_function_call(logger)
    def clear_context_documents(self) -> None:
        """Entfernt alle Kontextdokumente aus der Session."""
        try:
            previous_count = len(self.context_documents)
            self.context_documents.clear()
            
            logger.debug(
                "Kontextdokumente gelöscht",
                extra={
                    "session_id": self.id,
                    "cleared_documents": previous_count
                }
            )
            
        except Exception as e:
            logger.error(
                "Fehler beim Löschen der Kontextdokumente",
                extra={
                    "session_id": self.id,
                    "error": str(e)
                }
            )
            raise
    
    def __str__(self) -> str:
        """String-Repräsentation der Chat-Session."""
        return (
            f"ChatSession {self.id} "
            f"({len(self.messages)} Nachrichten, "
            f"{len(self.context_documents)} Kontextdokumente)"
        )
    
    class Config:
        """Pydantic Modell-Konfiguration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }