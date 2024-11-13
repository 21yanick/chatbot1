from typing import List, Dict, Any, Optional
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
from ..config.settings import settings
from ..config.logging_config import get_logger

logger = get_logger(__name__)

class ChatServiceImpl(ChatService):
    """Implementation of the chat service using LangChain and GPT-4."""
    
    def __init__(
        self,
        retrieval_service: RetrievalServiceImpl,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        self.retrieval_service = retrieval_service
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm = None
        self._sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the chat service and its dependencies."""
        try:
            await self.retrieval_service.initialize()
            self._llm = ChatOpenAI(
                model_name=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            logger.info(f"Initialized chat service with model: {self.model_name}")
        except Exception as e:
            raise ChatServiceError(f"Failed to initialize chat service: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        await self.retrieval_service.cleanup()
        self._sessions.clear()
        self._llm = None
        
        
    async def update_session_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """Update session metadata."""
        try:
            session = await self.get_session(session_id)
            if not session:
                return None

            # Update metadata
            session.metadata.update(metadata)
        
            # Return updated session
            return session
        
        except Exception as e:
            raise ChatServiceError(f"Failed to update session metadata: {str(e)}")
    
    async def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """Create a new chat session."""
        try:
            session_id = session_id or str(uuid4())
            session = ChatSession(
                id=session_id,
                metadata=metadata or {},
                messages=[]
            )
            
            # Add system message
            system_message = Message(
                content=settings.chat.system_prompt,
                role="system",
                metadata={"type": "system_prompt"}
            )
            session.add_message(system_message)
            
            async with self._lock:
                self._sessions[session_id] = session
            
            logger.info(f"Created chat session: {session_id}")
            return session
        
        except Exception as e:
            raise ChatServiceError(f"Failed to create session: {str(e)}")
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Retrieve a chat session by ID."""
        return self._sessions.get(session_id)
    
    async def add_message(
        self,
        session_id: str,
        message: Message,
        update_context: bool = True
    ) -> ChatSession:
        """Add a message to a chat session."""
        try:
            session = await self.get_session(session_id)
            if not session:
                raise ChatServiceError(f"Session not found: {session_id}")
        
            session.add_message(message)
        
            if update_context and message.role == "user":
                # Update context documents based on user message
                try:
                    relevant_docs = await self.retrieval_service.search_documents(
                        query=message.content,
                        limit=3
                    )
                    if relevant_docs:  # Nur wenn Dokumente gefunden wurden
                        session.metadata["context_documents"] = [
                            doc.id for doc in relevant_docs
                        ]
                except Exception as e:
                    logger.warning(f"Could not retrieve context documents: {str(e)}")
                    # Fahre ohne Kontext fort
        
            return session
        
        except Exception as e:
            raise ChatServiceError(f"Failed to add message: {str(e)}")
    
    def _prepare_context(self, documents: List[Document]) -> str:
        """Prepare context string from documents."""
        if not documents:
            return ""
        
        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(f"Document {i}:\n{doc.content}\n")
        
        return "\n".join(context_parts)
    
    def _create_prompt(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> ChatPromptTemplate:
        """Create a prompt with context and chat history."""
        template = """You are a vehicle expert assistant. Use the following context and chat history to answer the user's question.
If you don't know the answer, say so - don't make up information.

Context:
{context}

Chat History:
{chat_history}

User Question: {query}

Answer in the same language as the question. Be concise but thorough."""
        
        return ChatPromptTemplate.from_messages([
            SystemMessage(content=template)
        ])
    
    def _format_chat_history(self, messages: List[Message]) -> str:
        """Format chat history for prompt."""
        history = []
        for msg in messages:
            if msg.role != "system":
                history.append(f"{msg.role.capitalize()}: {msg.content}")
        return "\n".join(history) if history else "No previous messages."
    
    async def get_context(
        self,
        session_id: str,
        max_messages: Optional[int] = None,
        include_system: bool = True
    ) -> List[Message]:
        """Get the conversation context for a session."""
        try:
            session = await self.get_session(session_id)
            if not session:
                raise ChatServiceError(f"Session not found: {session_id}")
            
            messages = session.get_context(max_messages)
            if not include_system:
                messages = [msg for msg in messages if msg.role != "system"]
            
            return messages
        
        except Exception as e:
            raise ChatServiceError(f"Failed to get context: {str(e)}")
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        try:
            async with self._lock:
                if session_id in self._sessions:
                    del self._sessions[session_id]
                    logger.info(f"Deleted chat session: {session_id}")
                    return True
                return False
        
        except Exception as e:
            raise ChatServiceError(f"Failed to delete session: {str(e)}")
    
    async def get_response(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[List[Document]] = None
    ) -> Message:
        """
        Get a response from the assistant.
        
        Args:
            query: User's question
            session_id: Optional session ID for context
            context: Optional list of context documents
        
        Returns:
            Assistant's response message
        """
        try:
            # Get or create session
            session = None
            if session_id:
                session = await self.get_session(session_id)
            if not session:
                session = await self.create_session(session_id)
            
            # Create user message
            user_message = Message(
                content=query,
                role="user"
            )
            await self.add_message(session.id, user_message)
            
            # Get context documents if not provided
            context_docs = []
            if context is None and session.metadata.get("context_documents"):
                for doc_id in session.metadata["context_documents"]:
                    try:
                        doc = await self.retrieval_service.get_document(doc_id)
                        if doc:
                            context_docs.append(doc)
                    except Exception as e:
                        logger.warning(f"Could not retrieve document {doc_id}: {str(e)}")
                        continue
        
            # Use provided context or found context_docs
            context = context or context_docs
            
            # Prepare prompt inputs
            context_str = self._prepare_context(context or [])
            chat_history = self._format_chat_history(
                session.get_context(settings.chat.max_context_messages)
            )
            
            # Create and format prompt
            prompt = self._create_prompt(query, context_str, chat_history)
            
            # Get response from LLM
            response = await asyncio.to_thread(
                self._llm.predict_messages,
                [
                    SystemMessage(content=prompt.messages[0].content.format(
                        query=query,
                        context=context_str,
                        chat_history=chat_history
                    ))
                ]
            )
            
            # Create assistant message
            assistant_message = Message(
                content=response.content,
                role="assistant",
                metadata={
                    "context_documents": [doc.id for doc in (context or [])],
                    "model": self.model_name,
                    "temperature": self.temperature
                }
            )
            
            # Add to session
            await self.add_message(session.id, assistant_message, update_context=False)
            
            return assistant_message
        
        except Exception as e:
            raise ChatServiceError(f"Failed to get response: {str(e)}")