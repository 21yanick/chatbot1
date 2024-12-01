"""
State Manager Modul - Verwaltet den Anwendungszustand und die Service-Lebenszyklen

Dieses Modul implementiert den zentralen State Manager für die Streamlit-Anwendung.
Er ist verantwortlich für:
- Initialisierung und Verwaltung der Services
- Verwaltung des Chat-Verlaufs
- Fehlerbehandlung und Logging
- Session-Management
"""

import streamlit as st
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

from src.backend.models.chat import Message, ChatSession
from src.backend.services.chat_service import ChatServiceImpl
from src.backend.services.retrieval_service import RetrievalServiceImpl
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.document_processor import DocumentProcessor
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

class StateManager:
    """
    Zentraler State Manager der Anwendung.
    
    Verwaltet den gesamten Anwendungszustand einschließlich:
    - Service-Initialisierung und -Verwaltung
    - Chat-Session-Management
    - Fehlerbehandlung
    - Zustandssynchronisation
    """
    
    def __init__(self):
        """
        Initialisiert den StateManager und richtet den Basis-Zustand ein.
        Falls noch nicht vorhanden, werden die Grundeinstellungen in 
        Streamlits Session State gesetzt.
        """
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.logger.debug("Initialisiere StateManager")
        
        # Basis-Zustandsverwaltung einrichten
        self._initialize_session_state()
    
    def _initialize_session_state(self) -> None:
        """
        Initialisiert die Grundeinstellungen im Streamlit Session State.
        Wird nur ausgeführt, wenn der State noch nicht existiert.
        """
        with log_execution_time(self.logger, "session_state_initialization"):
            if "initialized" not in st.session_state:
                st.session_state.update({
                    "initialized": False,
                    "chat_history": [],
                    "session_id": str(uuid4()),
                    "error": None,
                    "last_activity": datetime.utcnow().isoformat(),
                    "debug_mode": False,
                    "metrics": {
                        "messages_sent": 0,
                        "errors_occurred": 0,
                        "last_response_time": None
                    }
                })
                self.logger.info("Neuer Session State initialisiert")

    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert alle erforderlichen Services und richtet die Chat-Session ein.
        
        Raises:
            Exception: Bei Fehlern während der Initialisierung
        """
        try:
            if not st.session_state.initialized:
                with log_execution_time(self.logger, "service_initialization"):
                    with request_context():
                        # Services initialisieren
                        services = await self._initialize_services()
                        
                        # Services im Session State speichern
                        st.session_state.update(services)
                        
                        # Chat-Session erstellen
                        chat_service: ChatServiceImpl = services["chat_service"]
                        session = await chat_service.create_session(
                            session_id=st.session_state.session_id,
                            metadata={
                                "created_at": datetime.utcnow().isoformat(),
                                "client_info": {
                                    "debug_mode": st.session_state.debug_mode
                                }
                            }
                        )
                        
                        st.session_state.initialized = True
                        self.logger.info(
                            "Services erfolgreich initialisiert",
                            extra={
                                "session_id": session.id,
                                "debug_mode": st.session_state.debug_mode
                            }
                        )
        
        except Exception as e:
            error_context = {
                "session_id": st.session_state.get("session_id"),
                "debug_mode": st.session_state.get("debug_mode", False)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Service-Initialisierung"
            )
            st.session_state.error = f"Initialisierungsfehler: {str(e)}"
            raise

    async def _initialize_services(self) -> Dict[str, Any]:
        """
        Initialisiert alle benötigten Backend-Services.
        
        Returns:
            Dict mit initialisierten Service-Instanzen
        """
        with log_execution_time(self.logger, "service_creation"):
            # Services erstellen
            embedding_service = EmbeddingService()
            document_processor = DocumentProcessor()
            retrieval_service = RetrievalServiceImpl(
                embedding_service=embedding_service,
                document_processor=document_processor
            )
            chat_service = ChatServiceImpl(
                retrieval_service=retrieval_service
            )
            
            # Services initialisieren
            await embedding_service.initialize()
            await document_processor.initialize()
            await retrieval_service.initialize()
            await chat_service.initialize()
            
            return {
                "embedding_service": embedding_service,
                "document_processor": document_processor,
                "retrieval_service": retrieval_service,
                "chat_service": chat_service
            }

    @log_function_call(logger)
    def get_messages(self) -> List[Message]:
        """
        Gibt alle Nachrichten der aktuellen Chat-Session zurück.
        
        Returns:
            Liste aller Chat-Nachrichten
        """
        messages = st.session_state.chat_history
        self.logger.debug(
            f"Chat-Verlauf abgerufen",
            extra={
                "message_count": len(messages),
                "session_id": st.session_state.session_id
            }
        )
        return messages

    @log_function_call(logger)
    async def send_message(self, content: str):
        """
        Sendet eine Nachricht und streamt die Antwort vom Chatbot.
    
        Verarbeitet die Benutzereingabe und gibt die Antwort
        als asynchronen Stream zurück.
    
        Args:
            content: Nachrichteninhalt
            
        Yields:
            str: Chunks der Chatbot-Antwort
        
        Raises:
            Exception: Bei Fehlern in der Nachrichtenverarbeitung
        """
        try:
            if not content.strip():
                self.logger.debug("Leere Nachricht ignoriert")
                return
                
            with request_context():
                with log_execution_time(self.logger, "message_processing"):
                    # Benutzernachricht erstellen
                    user_message = Message(
                        content=content.strip(),
                        role="user",
                        metadata={
                            "timestamp": datetime.utcnow().isoformat(),
                            "session_id": st.session_state.session_id
                        }
                    )
                    
                    # Zum Chat-Verlauf hinzufügen
                    st.session_state.chat_history.append(user_message)
                    
                    # Metriken aktualisieren
                    st.session_state.metrics["messages_sent"] += 1
                    st.session_state.last_activity = datetime.utcnow().isoformat()
                    
                    # Antwort vom Chat-Service als Stream verarbeiten
                    start_time = datetime.utcnow()
                    chat_service: ChatServiceImpl = st.session_state.chat_service
                    full_response = ""
                    
                    async for chunk in chat_service.get_response(
                        query=content,
                        session_id=st.session_state.session_id
                    ):
                        full_response += chunk
                        yield chunk
                    
                    # Response-Zeit messen
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    st.session_state.metrics["last_response_time"] = response_time
                    
                    # Vollständige Antwort zum Chat-Verlauf hinzufügen
                    assistant_message = Message(
                        content=full_response,
                        role="assistant",
                        metadata={
                            "timestamp": datetime.utcnow().isoformat(),
                            "response_time": response_time,
                            "session_id": st.session_state.session_id
                        }
                    )
                    st.session_state.chat_history.append(assistant_message)
                    
                    self.logger.info(
                        "Nachricht erfolgreich verarbeitet",
                        extra={
                            "session_id": st.session_state.session_id,
                            "response_time": response_time,
                            "message_length": len(content),
                            "response_length": len(full_response)
                        }
                    )
        
        except Exception as e:
            error_context = {
                "session_id": st.session_state.session_id,
                "message_length": len(content),
                "total_messages": len(st.session_state.chat_history)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Nachrichtenverarbeitung"
            )
            st.session_state.metrics["errors_occurred"] += 1
            st.session_state.error = f"Fehler bei der Verarbeitung: {str(e)}"
            raise

    @log_function_call(logger)
    def clear_chat(self) -> None:
        """Löscht den Chat-Verlauf und setzt relevante Metriken zurück."""
        with log_execution_time(self.logger, "chat_cleanup"):
            old_count = len(st.session_state.chat_history)
            st.session_state.chat_history = []
            st.session_state.metrics["messages_sent"] = 0
            
            self.logger.info(
                "Chat-Verlauf gelöscht",
                extra={
                    "deleted_messages": old_count,
                    "session_id": st.session_state.session_id
                }
            )

    @log_function_call(logger)
    def has_error(self) -> bool:
        """
        Prüft ob ein Fehler vorliegt.
        
        Returns:
            bool: True wenn ein Fehler vorliegt, sonst False
        """
        return bool(st.session_state.error)

    @log_function_call(logger)
    def get_error(self) -> Optional[str]:
        """
        Gibt die aktuelle Fehlermeldung zurück.
        
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        error = st.session_state.error
        if error:
            self.logger.debug(
                f"Fehler abgerufen",
                extra={
                    "error_message": error,
                    "session_id": st.session_state.session_id
                }
            )
        return error

    @log_function_call(logger)
    def clear_error(self) -> None:
        """Löscht die aktuelle Fehlermeldung."""
        if st.session_state.error:
            self.logger.debug(
                "Fehler gelöscht",
                extra={"session_id": st.session_state.session_id}
            )
            st.session_state.error = None

    @log_function_call(logger)
    def get_metrics(self) -> Dict[str, Any]:
        """
        Gibt die aktuellen Nutzungsmetriken zurück.
        
        Returns:
            Dict mit Metriken zur aktuellen Session
        """
        metrics = st.session_state.metrics.copy()
        metrics.update({
            "session_duration": (
                datetime.utcnow() - 
                datetime.fromisoformat(st.session_state.last_activity)
            ).total_seconds(),
            "total_messages": len(st.session_state.chat_history)
        })
        
        self.logger.debug(
            "Metriken abgerufen",
            extra={
                "session_id": st.session_state.session_id,
                "metrics": metrics
            }
        )
        
        return metrics