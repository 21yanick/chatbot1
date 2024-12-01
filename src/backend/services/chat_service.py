"""
Chat-Service-Modul für die Verarbeitung von Benutzeranfragen und Konversationen.
Implementiert die Kernlogik für den dialogbasierten Zugriff auf Fachinformationen.
"""

from typing import AsyncGenerator, List, Dict, Any, Optional
import asyncio
from uuid import uuid4
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage, AIMessage

from ..models.chat import ChatSession, Message
from ..models.document import Document
from ..interfaces.chat import ChatService, ChatServiceError
from .retrieval_service import RetrievalServiceImpl
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

class ChatServiceImpl(ChatService):
    """
    Implementierung des Chat-Services mit LangChain und 4.
    
    Verwaltet Chat-Sessions, verarbeitet Benutzeranfragen und generiert
    kontextbezogene Antworten unter Verwendung von LLMs.
    """
    
    def __init__(
        self,
        retrieval_service: RetrievalServiceImpl,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Initialisiert den Chat-Service.
        
        Args:
            retrieval_service: Service für Dokumenten-Retrieval
            model_name: Optional - Name des zu verwendenden LLM-Modells, default aus settings
            temperature: Optional - Kreativität des Modells (0-1), default aus settings
            max_tokens: Optional - Maximale Token-Länge der Antworten, default aus settings
        """
        self.retrieval_service = retrieval_service
        self.model_name = model_name or settings.api.openai_model
        self.temperature = temperature or settings.chat.temperature
        self.max_tokens = max_tokens or settings.chat.max_tokens
        self._llm = None
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert den Chat-Service und seine Abhängigkeiten.
        
        Raises:
            ChatServiceError: Bei Initialisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "chat_service_initialization"):
                await self.retrieval_service.initialize()
                self._llm = ChatOpenAI(
                    model_name=self.model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                
            self.logger.info(
                "Chat-Service initialisiert",
                extra={
                    "model": self.model_name,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens
                }
            )
            
        except Exception as e:
            error_context = {
                "model": self.model_name,
                "temperature": self.temperature
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Chat-Service-Initialisierung"
            )
            raise ChatServiceError(f"Chat-Service-Initialisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Service-Ressourcen."""
        with log_execution_time(self.logger, "cleanup"):
            await self.retrieval_service.cleanup()
            self._sessions.clear()
            self._llm = None
            self.logger.info("Chat-Service-Ressourcen bereinigt")
    
    @log_function_call(logger)
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
            ChatServiceError: Bei Aktualisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "update_metadata"):
                session = await self.get_session(session_id)
                if not session:
                    self.logger.warning(
                        f"Session nicht gefunden",
                        extra={"session_id": session_id}
                    )
                    return None

                session.metadata.update(metadata)
                self.logger.info(
                    f"Session-Metadaten aktualisiert",
                    extra={
                        "session_id": session_id,
                        "metadata_keys": list(metadata.keys())
                    }
                )
                return session
            
        except Exception as e:
            error_context = {
                "session_id": session_id,
                "metadata_keys": list(metadata.keys())
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Metadaten-Aktualisierung"
            )
            raise ChatServiceError(f"Metadaten-Aktualisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
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
            ChatServiceError: Bei Erstellungsfehlern
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
                    f"Neue Chat-Session erstellt",
                    extra={
                        "session_id": session_id,
                        "has_metadata": bool(metadata)
                    }
                )
                return session
            
        except Exception as e:
            error_context = {
                "session_id": session_id,
                "has_metadata": bool(metadata)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Session-Erstellung"
            )
            raise ChatServiceError(f"Session-Erstellung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
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
                f"Session abgerufen",
                extra={"session_id": session_id}
            )
        else:
            self.logger.warning(
                f"Session nicht gefunden",
                extra={"session_id": session_id}
            )
        return session
    
    @log_function_call(logger)
    async def add_message(
        self,
        session_id: str,
        message: Message,
        update_context: bool = True
    ) -> ChatSession:
        """
        Fügt eine Nachricht zu einer Chat-Session hinzu.
        
        Args:
            session_id: ID der Session
            message: Hinzuzufügende Nachricht
            update_context: Ob der Kontext aktualisiert werden soll
            
        Returns:
            Aktualisierte ChatSession
            
        Raises:
            ChatServiceError: Bei Fehlern beim Hinzufügen
        """
        try:
            with log_execution_time(self.logger, "add_message"):
                session = await self.get_session(session_id)
                if not session:
                    raise ChatServiceError(f"Session nicht gefunden: {session_id}")
            
                session.add_message(message)
            
                if update_context and message.role == "user":
                    try:
                        relevant_docs = await self.retrieval_service.search_documents(
                            query=message.content,
                            limit=3
                        )
                        if relevant_docs:
                            session.metadata["context_documents"] = [
                                doc.id for doc in relevant_docs
                            ]
                            self.logger.info(
                                f"Kontext-Dokumente aktualisiert",
                                extra={
                                    "session_id": session_id,
                                    "doc_count": len(relevant_docs)
                                }
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Kontext-Aktualisierung fehlgeschlagen: {str(e)}",
                            extra={"session_id": session_id}
                        )
            
                return session
            
        except Exception as e:
            error_context = {
                "session_id": session_id,
                "message_role": message.role
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Hinzufügen einer Nachricht"
            )
            raise ChatServiceError(f"Nachricht konnte nicht hinzugefügt werden: {str(e)}")

    def _prepare_context(self, documents: List[Document]) -> str:
        """
        Bereitet den Kontext-String aus Dokumenten vor.
        
        Args:
            documents: Liste der Kontext-Dokumente
            
        Returns:
            Formatierter Kontext-String
        """
        if not documents:
            return ""
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(f"Dokument {i}:\n{doc.content}\n")
        
        return "\n".join(context_parts)
    
    def _create_prompt(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> ChatPromptTemplate:
        """
        Erstellt einen Prompt mit Kontext und Chat-Verlauf.
        
        Args:
            query: Benutzeranfrage
            context: Kontext-String
            chat_history: Optionaler Chat-Verlauf
            
        Returns:
            Formatierter ChatPromptTemplate
        """
        template = """Sie sind ein Fahrzeug-Experten-Assistent. Nutzen Sie den folgenden Kontext und Chat-Verlauf,
        um die Frage des Benutzers zu beantworten. Wenn Sie die Antwort nicht wissen, sagen Sie das ehrlich - 
        erfinden Sie keine Informationen.

        Kontext:
        {context}

        Chat-Verlauf:
        {chat_history}

        Benutzeranfrage: {query}

        Antworten Sie in der gleichen Sprache wie die Anfrage. Seien Sie präzise aber gründlich."""
        
        return ChatPromptTemplate.from_messages([
            SystemMessage(content=template)
        ])
    
    def _format_chat_history(self, messages: List[Message]) -> str:
        """
        Formatiert den Chat-Verlauf für den Prompt.
        
        Args:
            messages: Liste der Chat-Nachrichten
            
        Returns:
            Formatierter Chat-Verlauf als String
        """
        history = []
        for msg in messages:
            if msg.role != "system":
                history.append(f"{msg.role.capitalize()}: {msg.content}")
        return "\n".join(history) if history else "Keine vorherigen Nachrichten."
    
    @log_function_call(logger)
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
            ChatServiceError: Bei Fehlern beim Abrufen
        """
        try:
            with log_execution_time(self.logger, "get_context"):
                session = await self.get_session(session_id)
                if not session:
                    raise ChatServiceError(f"Session nicht gefunden: {session_id}")
                
                messages = session.get_context(max_messages)
                if not include_system:
                    messages = [msg for msg in messages if msg.role != "system"]
                
                self.logger.debug(
                    f"Kontext abgerufen",
                    extra={
                        "session_id": session_id,
                        "message_count": len(messages)
                    }
                )
                return messages
            
        except Exception as e:
            error_context = {
                "session_id": session_id,
                "max_messages": max_messages
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Abrufen des Kontexts"
            )
            raise ChatServiceError(f"Kontext konnte nicht abgerufen werden: {str(e)}")
    
    @log_function_call(logger)
    async def delete_session(self, session_id: str) -> bool:
        """
        Löscht eine Chat-Session.
        
        Args:
            session_id: ID der zu löschenden Session
            
        Returns:
            True wenn erfolgreich gelöscht
            
        Raises:
            ChatServiceError: Bei Fehlern beim Löschen
        """
        try:
            with log_execution_time(self.logger, "delete_session"):
                async with self._lock:
                    if session_id in self._sessions:
                        del self._sessions[session_id]
                        self.logger.info(
                            f"Chat-Session gelöscht",
                            extra={"session_id": session_id}
                        )
                        return True
                    
                    self.logger.warning(
                        f"Session zum Löschen nicht gefunden",
                        extra={"session_id": session_id}
                    )
                    return False
            
        except Exception as e:
            error_context = {"session_id": session_id}
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Löschen der Session"
            )
            raise ChatServiceError(f"Session konnte nicht gelöscht werden: {str(e)}")
    
    @log_function_call(logger)
    async def get_response(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[List[Document]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generiert eine Antwort des Assistenten als Stream.
    
        Verarbeitet die Benutzeranfrage unter Berücksichtigung des Kontexts
        und der Chat-Historie, um eine passende Antwort zu generieren.
        Die Antwort wird als Stream zurückgegeben, um eine flüssigere
        Benutzererfahrung zu ermöglichen.
    
        Args:
            query: Benutzeranfrage
            session_id: Optionale Session-ID für Kontext
            context: Optionale Liste von Kontext-Dokumenten
            
        Yields:
            str: Antwort-Chunks im Stream
            
        Raises:
            ChatServiceError: Bei Fehlern in der Antwortgenerierung
        """
        try:
            with log_execution_time(self.logger, "generate_response"):
                with request_context():
                    # Session verwalten
                    session = None
                    if session_id:
                        session = await self.get_session(session_id)
                    if not session:
                        session = await self.create_session(session_id)
                
                    # Benutzernachricht erstellen und hinzufügen
                    user_message = Message(
                        content=query,
                        role="user"
                    )
                    await self.add_message(session.id, user_message)
                
                    # Kontextdokumente abrufen
                    context_docs = []
                    if context is None and session.metadata.get("context_documents"):
                        for doc_id in session.metadata["context_documents"]:
                            try:
                                doc = await self.retrieval_service.get_document(doc_id)
                                if doc:
                                    context_docs.append(doc)
                            except Exception as e:
                                self.logger.warning(
                                    f"Dokument konnte nicht abgerufen werden",
                                    extra={
                                        "document_id": doc_id,
                                        "error": str(e)
                                    }
                                )
                                continue
                
                    # Kontext vorbereiten
                    context = context or context_docs
                    context_str = self._prepare_context(context or [])
                    chat_history = self._format_chat_history(
                        session.get_context(settings.chat.max_context_messages)
                    )
                
                    # Prompt erstellen und formatieren
                    prompt = self._create_prompt(query, context_str, chat_history)
                
                    self.logger.debug(
                        "Prompt vorbereitet",
                        extra={
                            "context_length": len(context_str),
                            "history_length": len(chat_history)
                        }
                    )
                
                    # Streaming LLM konfigurieren
                    streaming_llm = ChatOpenAI(
                        model_name=self.model_name,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        streaming=True
                    )
                
                    # Antwort generieren und streamen
                    response_chunks = []
                    async for chunk in streaming_llm.astream([
                        SystemMessage(content=prompt.messages[0].content.format(
                            query=query,
                            context=context_str,
                            chat_history=chat_history
                        ))
                    ]):
                        response_chunks.append(chunk.content)
                        yield chunk.content
                
                    # Vollständige Antwort zusammenbauen und speichern
                    complete_response = "".join(response_chunks)
                    assistant_message = Message(
                        content=complete_response,
                        role="assistant",
                        metadata={
                            "context_documents": [doc.id for doc in (context or [])],
                            "model": self.model_name,
                            "temperature": self.temperature,
                            "response_time": datetime.utcnow().isoformat()
                        }
                    )
                
                    # Zur Session hinzufügen
                    await self.add_message(session.id, assistant_message, update_context=False)
                
                    self.logger.info(
                        f"Antwort generiert",
                        extra={
                            "session_id": session.id,
                            "response_length": len(complete_response),
                            "context_docs_used": len(context or [])
                        }
                    )
                
        except Exception as e:
            error_context = {
                "session_id": session_id,
                "query_length": len(query),
                "context_docs": len(context or [])
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei der Antwortgenerierung"
            )
            raise ChatServiceError(f"Antwort konnte nicht generiert werden: {str(e)}")