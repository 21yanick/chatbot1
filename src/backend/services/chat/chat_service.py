"""
Chat-Service-Modul für die Verarbeitung von Benutzeranfragen und Konversationen.
Orchestriert die verschiedenen Manager für Session-, Kontext- und Prompt-Verwaltung.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage
from datetime import datetime

from ...models.chat import Message, ChatSession
from ...models.document import Document
from ...interfaces.chat import ChatService, ChatServiceError
from .managers.session_manager import SessionManager
from .managers.context_manager import ContextManager
from .managers.prompt_manager import PromptManager
from .utils.decorators import combined_logging_decorator
from src.config.settings import settings
from src.config.logging_config import get_logger

class ChatServiceImpl(ChatService):
    """
    Implementierung des Chat-Services mit LangChain und GPT-4.
    
    Koordiniert:
    - Session-Verwaltung über SessionManager
    - Kontext-Aufbereitung über ContextManager
    - Prompt-Erstellung über PromptManager
    """
    
    def __init__(
        self,
        retrieval_service,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ):
        """
        Initialisiert den Chat-Service und seine Manager.
        
        Args:
            retrieval_service: Service für Dokumenten-Retrieval
            model_name: Optional - Name des zu verwendenden LLM-Modells
            temperature: Optional - Kreativität des Modells (0-1)
            max_tokens: Optional - Maximale Token-Länge der Antworten
        """
        self.retrieval_service = retrieval_service
        self.model_name = model_name or settings.api.openai_model
        self.temperature = temperature or settings.chat.temperature
        self.max_tokens = max_tokens or settings.chat.max_tokens
        
        # Manager initialisieren
        self.session_manager = SessionManager()
        self.context_manager = ContextManager()
        self.prompt_manager = PromptManager()
        
        self._llm = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    @combined_logging_decorator
    async def initialize(self) -> None:
        """
        Initialisiert den Chat-Service und seine Abhängigkeiten.
        
        Raises:
            ChatServiceError: Bei Initialisierungsfehlern
        """
        try:
            await self.retrieval_service.initialize()
            self._llm = ChatOpenAI(
                api_key=settings.openai_api_key,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            self.logger.debug(
                "LLM Konfiguration",
                extra={
                    "api_key_set": bool(settings.openai_api_key),
                    "model": self.model_name,
                    "temperature": self.temperature
                }
            )
            
        except Exception as e:
            raise ChatServiceError(f"Chat-Service-Initialisierung fehlgeschlagen: {str(e)}")

    @combined_logging_decorator
    async def cleanup(self) -> None:
        """Bereinigt Service-Ressourcen."""
        await self.retrieval_service.cleanup()
        self._llm = None

    @combined_logging_decorator
    async def get_response(
        self,
        query: str,
        session_id: Optional[str] = None,
        context_docs: Optional[List[Document]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Generiert eine Antwort des Assistenten als Stream.
        
        Args:
            query: Benutzeranfrage
            session_id: Optionale Session-ID für Kontext
            context_docs: Optionale Liste von Kontext-Dokumenten
            
        Yields:
            str: Antwort-Chunks im Stream
            
        Raises:
            ChatServiceError: Bei Fehlern in der Antwortgenerierung
        """
        try:
            # Session verwalten
            session = None
            if session_id:
                session = await self.session_manager.get_session(session_id)
            if not session:
                session = await self.session_manager.create_session(session_id)
            
            # Benutzernachricht zur Session hinzufügen
            user_message = Message(
                content=query,
                role="user"
            )
            await self.session_manager.add_message(session.id, user_message)
            
            # Kontext vorbereiten
            if context_docs is None and session.metadata.get("context_documents"):
                context_docs = []
                for doc_id in session.metadata["context_documents"]:
                    doc = await self.retrieval_service.get_document(doc_id)
                    if doc:
                        context_docs.append(doc)
            
            # Chat-Verlauf und Kontext aufbereiten
            messages = await self.session_manager.get_context(
                session.id,
                settings.chat.max_context_messages
            )
            context = self.context_manager.prepare_combined_context(
                query=query,
                documents=context_docs or [],
                messages=messages
            )
            
            # Prompt formatieren
            formatted_prompt = self.prompt_manager.format_prompt(
                template_name="default",
                variables={
                    "query": query,
                    "context": context["documents"],
                    "chat_history": context["chat_history"]
                }
            )
            
            self.logger.debug(
                "Prompt vorbereitet",
                extra={
                    "prompt_length": len(formatted_prompt),
                    "context_length": len(context["documents"]),
                    "history_length": len(context["chat_history"])
                }
            )
            
            # Streaming LLM konfigurieren
            streaming_llm = ChatOpenAI(
                api_key=settings.openai_api_key,
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                streaming=True
            )
            
            # Antwort generieren und streamen
            response_chunks = []
            async for chunk in streaming_llm.astream([SystemMessage(content=formatted_prompt)]):
                response_chunks.append(chunk.content)
                yield chunk.content
            
            # Vollständige Antwort zur Session hinzufügen
            complete_response = "".join(response_chunks)
            assistant_message = Message(
                content=complete_response,
                role="assistant",
                metadata={
                    "context_documents": [doc.id for doc in (context_docs or [])],
                    "model": self.model_name,
                    "temperature": self.temperature,
                    "response_time": datetime.utcnow().isoformat()
                }
            )
            await self.session_manager.add_message(session.id, assistant_message)
            
            self.logger.info(
                "Antwort generiert",
                extra={
                    "response_length": len(complete_response),
                    "session_id": session.id,
                    "context_docs_used": len(context_docs or [])
                }
            )
            
        except Exception as e:
            error_msg = f"Antwort konnte nicht generiert werden: {str(e)}"
            self.logger.error(
                error_msg,
                extra={
                    "query": query,
                    "session_id": session_id if session_id else "None"
                },
                exc_info=True
            )
            raise ChatServiceError(error_msg)

    # Delegate-Methoden für Session-Management
    
    @combined_logging_decorator
    async def create_session(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> ChatSession:
        """Delegiert Session-Erstellung an SessionManager."""
        return await self.session_manager.create_session(session_id, metadata)

    @combined_logging_decorator
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Delegiert Session-Abruf an SessionManager."""
        return await self.session_manager.get_session(session_id)

    @combined_logging_decorator
    async def update_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> Optional[ChatSession]:
        """Delegiert Metadaten-Aktualisierung an SessionManager."""
        return await self.session_manager.update_session_metadata(session_id, metadata)

    @combined_logging_decorator
    async def delete_session(self, session_id: str) -> bool:
        """Delegiert Session-Löschung an SessionManager."""
        return await self.session_manager.delete_session(session_id)