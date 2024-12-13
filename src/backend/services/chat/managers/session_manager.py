"""
Session Manager Modul für die Verwaltung von Chat-Sessions.
Behandelt die Erstellung, Aktualisierung und Löschung von Chat-Sessions.
"""

from typing import Dict, Any, List, Optional
import asyncio
from uuid import uuid4
from datetime import datetime

from src.backend.models.chat import ChatSession, Message
from src.config.settings import settings
from src.config.logging_config import get_logger, log_execution_time

class SessionManagerError(Exception):
    """Basisklasse für SessionManager-spezifische Fehler."""
    pass

class SessionManager:
    """
    Verwaltet Chat-Sessions und deren Lebenszyklus.
    
    Verantwortlich für:
    - Erstellung neuer Sessions
    - Abrufen existierender Sessions
    - Aktualisierung von Session-Metadaten
    - Löschung von Sessions
    """
    
    def __init__(self):
        """Initialisiert den SessionManager."""
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    async def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """
        Erstellt eine neue Chat-Session.
        
        Args:
            session_id: Optionale Session-ID
            metadata: Optionale initiale Metadaten
            
        Returns:
            Neue ChatSession
            
        Raises:
            SessionManagerError: Bei Erstellungsfehlern
        """
        try:
            with log_execution_time(self.logger, "create_session"):
                session_id = session_id or str(uuid4())
                session = ChatSession(
                    id=session_id,
                    metadata=metadata or {},
                    messages=[]
                )
                
                # System-Nachricht hinzufügen
                system_message = Message(
                    content=settings.chat.system_prompt,
                    role="system",
                    metadata={"type": "system_prompt"}
                )
                session.add_message(system_message)
                
                async with self._lock:
                    self._sessions[session_id] = session
                
                self.logger.info(
                    "Neue Chat-Session erstellt",
                    extra={
                        "session_id": session_id,
                        "has_metadata": bool(metadata)
                    }
                )
                return session
            
        except Exception as e:
            self.logger.error(
                f"Session-Erstellung fehlgeschlagen: {str(e)}",
                extra={
                    "session_id": session_id,
                    "has_metadata": bool(metadata)
                }
            )
            raise SessionManagerError(f"Session-Erstellung fehlgeschlagen: {str(e)}")

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Ruft eine Chat-Session anhand ihrer ID ab.
        
        Args:
            session_id: ID der gewünschten Session
            
        Returns:
            ChatSession oder None wenn nicht gefunden
        """
        session = self._sessions.get(session_id)
        if session:
            self.logger.debug(
                "Session abgerufen",
                extra={"session_id": session_id}
            )
        else:
            self.logger.warning(
                "Session nicht gefunden",
                extra={"session_id": session_id}
            )
        return session

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
            Aktualisierte ChatSession oder None wenn nicht gefunden
            
        Raises:
            SessionManagerError: Bei Aktualisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "update_metadata"):
                session = await self.get_session(session_id)
                if not session:
                    self.logger.warning(
                        "Session nicht gefunden",
                        extra={"session_id": session_id}
                    )
                    return None

                session.metadata.update(metadata)
                self.logger.info(
                    "Session-Metadaten aktualisiert",
                    extra={
                        "session_id": session_id,
                        "metadata_keys": list(metadata.keys())
                    }
                )
                return session
            
        except Exception as e:
            self.logger.error(
                f"Metadaten-Aktualisierung fehlgeschlagen: {str(e)}",
                extra={
                    "session_id": session_id,
                    "metadata_keys": list(metadata.keys())
                }
            )
            raise SessionManagerError(f"Metadaten-Aktualisierung fehlgeschlagen: {str(e)}")

    async def delete_session(self, session_id: str) -> bool:
        """
        Löscht eine Chat-Session.
        
        Args:
            session_id: ID der zu löschenden Session
            
        Returns:
            True wenn erfolgreich gelöscht
            
        Raises:
            SessionManagerError: Bei Fehlern beim Löschen
        """
        try:
            with log_execution_time(self.logger, "delete_session"):
                async with self._lock:
                    if session_id in self._sessions:
                        del self._sessions[session_id]
                        self.logger.info(
                            "Chat-Session gelöscht",
                            extra={"session_id": session_id}
                        )
                        return True
                    
                    self.logger.warning(
                        "Session zum Löschen nicht gefunden",
                        extra={"session_id": session_id}
                    )
                    return False
            
        except Exception as e:
            self.logger.error(
                f"Session konnte nicht gelöscht werden: {str(e)}",
                extra={"session_id": session_id}
            )
            raise SessionManagerError(f"Session konnte nicht gelöscht werden: {str(e)}")

    async def add_message(
        self,
        session_id: str,
        message: Message
    ) -> ChatSession:
        """
        Fügt eine Nachricht zu einer Chat-Session hinzu.
        
        Args:
            session_id: ID der Session
            message: Hinzuzufügende Nachricht
            
        Returns:
            Aktualisierte ChatSession
            
        Raises:
            SessionManagerError: Bei Fehlern beim Hinzufügen
        """
        try:
            with log_execution_time(self.logger, "add_message"):
                session = await self.get_session(session_id)
                if not session:
                    raise SessionManagerError(f"Session nicht gefunden: {session_id}")
            
                session.add_message(message)
                
                self.logger.info(
                    "Nachricht zur Session hinzugefügt",
                    extra={
                        "session_id": session_id,
                        "message_role": message.role
                    }
                )
                
                return session
            
        except Exception as e:
            self.logger.error(
                f"Nachricht konnte nicht hinzugefügt werden: {str(e)}",
                extra={
                    "session_id": session_id,
                    "message_role": message.role
                }
            )
            raise SessionManagerError(f"Nachricht konnte nicht hinzugefügt werden: {str(e)}")

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
            max_messages: Maximale Anzahl der Nachrichten
            include_system: Ob System-Nachrichten einbezogen werden sollen
            
        Returns:
            Liste von Kontext-Nachrichten
            
        Raises:
            SessionManagerError: Bei Fehlern beim Abrufen
        """
        try:
            with log_execution_time(self.logger, "get_context"):
                session = await self.get_session(session_id)
                if not session:
                    raise SessionManagerError(f"Session nicht gefunden: {session_id}")
                
                messages = session.get_context(max_messages)
                if not include_system:
                    messages = [msg for msg in messages if msg.role != "system"]
                
                self.logger.debug(
                    "Kontext abgerufen",
                    extra={
                        "session_id": session_id,
                        "message_count": len(messages)
                    }
                )
                return messages
            
        except Exception as e:
            self.logger.error(
                f"Kontext konnte nicht abgerufen werden: {str(e)}",
                extra={
                    "session_id": session_id,
                    "max_messages": max_messages
                }
            )
            raise SessionManagerError(f"Kontext konnte nicht abgerufen werden: {str(e)}")