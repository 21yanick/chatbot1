"""
Chat-Service-Interface-Modul.
Definiert die Schnittstelle für die Chat-Funktionalität und Session-Verwaltung.
"""

from typing import List, Optional, Dict, Any
from abc import abstractmethod

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..models.chat import ChatSession, Message
from .base import BaseService, ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class ChatServiceError(ServiceError):
    """
    Spezifische Exception für Chat-Service-Fehler.
    
    Erweitert die Basis-ServiceError um chat-spezifische Fehlerbehandlung.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialisiert die ChatServiceError Exception.
        
        Args:
            message: Beschreibende Fehlermeldung
            details: Optionale zusätzliche Fehlerdetails
        """
        super().__init__(f"Chat-Service-Fehler: {message}", details)

class ChatService(BaseService):
    """
    Interface für chat-bezogene Operationen.
    
    Definiert die grundlegende Schnittstelle für:
    - Session-Verwaltung
    - Nachrichtenverarbeitung
    - Kontext-Management
    - Metadaten-Verwaltung
    """
    
    def __init__(self):
        """Initialisiert den Chat-Service mit einem spezifischen Logger."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    @abstractmethod
    async def create_session(
        self, 
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        Erstellt eine neue Chat-Session.
        
        Args:
            session_id: Optionale benutzerdefinierte Session-ID
            metadata: Optionale initiale Metadaten
            
        Returns:
            Neu erstellte ChatSession
            
        Raises:
            ChatServiceError: Bei Erstellungsfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Ruft eine Chat-Session anhand ihrer ID ab.
        
        Args:
            session_id: ID der gewünschten Session
            
        Returns:
            ChatSession oder None falls nicht gefunden
            
        Raises:
            ChatServiceError: Bei Abruffehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def add_message(
        self, 
        session_id: str, 
        message: Message,
        update_context: bool = True
    ) -> ChatSession:
        """
        Fügt eine Nachricht zu einer Chat-Session hinzu.
        
        Args:
            session_id: ID der Session für die Nachricht
            message: Hinzuzufügende Nachricht
            update_context: Ob der Kontext basierend auf der Nachricht aktualisiert werden soll
            
        Returns:
            Aktualisierte ChatSession
            
        Raises:
            ChatServiceError: Bei Fehlern beim Hinzufügen der Nachricht
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def get_context(
        self, 
        session_id: str, 
        max_messages: Optional[int] = None,
        include_system: bool = True
    ) -> List[Message]:
        """
        Ruft den Konversationskontext einer Session ab.
        
        Args:
            session_id: ID der Session
            max_messages: Maximale Anzahl zurückzugebender Nachrichten
            include_system: Ob System-Nachrichten einbezogen werden sollen
            
        Returns:
            Liste der Kontext-Nachrichten
            
        Raises:
            ChatServiceError: Bei Fehlern beim Abrufen des Kontexts
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """
        Löscht eine Chat-Session.
        
        Args:
            session_id: ID der zu löschenden Session
            
        Returns:
            True wenn erfolgreich gelöscht, False falls nicht gefunden
            
        Raises:
            ChatServiceError: Bei Löschfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """
        Aktualisiert die Metadaten einer Chat-Session.
        
        Args:
            session_id: ID der zu aktualisierenden Session
            metadata: Neue Metadaten
            
        Returns:
            Aktualisierte ChatSession oder None falls nicht gefunden
            
        Raises:
            ChatServiceError: Bei Aktualisierungsfehlern
        """
        pass