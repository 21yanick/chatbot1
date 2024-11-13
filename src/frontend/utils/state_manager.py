import streamlit as st
from typing import List, Optional
from src.backend.models.chat import Message, ChatSession
from src.backend.services.chat_service import ChatServiceImpl
from src.backend.services.retrieval_service import RetrievalServiceImpl
from src.backend.services.embedding_service import EmbeddingService
from src.backend.services.document_processor import DocumentProcessor
from src.config.logging_config import get_logger

logger = get_logger(__name__)

class StateManager:
    """Manages application state and service lifecycle."""
    
    def __init__(self):
        if "initialized" not in st.session_state:
            st.session_state.initialized = False
            st.session_state.chat_history = []
            st.session_state.session_id = None
            st.session_state.error = None
    
    async def initialize(self) -> None:
        """Initialize services and session state."""
        try:
            if not st.session_state.initialized:
                # Initialize services
                embedding_service = EmbeddingService()
                document_processor = DocumentProcessor()
                
                retrieval_service = RetrievalServiceImpl(
                    embedding_service=embedding_service,
                    document_processor=document_processor
                )
                
                chat_service = ChatServiceImpl(
                    retrieval_service=retrieval_service
                )
                
                # Initialize all services
                await embedding_service.initialize()
                await document_processor.initialize()
                await retrieval_service.initialize()
                await chat_service.initialize()
                
                # Store in session state
                st.session_state.embedding_service = embedding_service
                st.session_state.document_processor = document_processor
                st.session_state.retrieval_service = retrieval_service
                st.session_state.chat_service = chat_service
                
                # Create new chat session
                session = await chat_service.create_session()
                st.session_state.session_id = session.id
                
                st.session_state.initialized = True
                logger.info("Services initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            st.session_state.error = f"Initialization error: {str(e)}"
            raise
    
    def get_messages(self) -> List[Message]:
        """Get all messages in the current chat session."""
        return st.session_state.chat_history
    
    async def send_message(self, content: str) -> Optional[Message]:
        """Send a message and get response from the chatbot."""
        try:
            if not content.strip():
                return None
            
            # Create user message
            user_message = Message(
                content=content.strip(),
                role="user"
            )
            
            # Add to chat history
            st.session_state.chat_history.append(user_message)
            
            # Get response from chat service
            chat_service: ChatServiceImpl = st.session_state.chat_service
            response = await chat_service.get_response(
                query=content,
                session_id=st.session_state.session_id
            )
            
            # Add response to chat history
            st.session_state.chat_history.append(response)
            
            return response
        
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            st.session_state.error = f"Failed to get response: {str(e)}"
            return None
    
    def clear_chat(self) -> None:
        """Clear the chat history."""
        st.session_state.chat_history = []
    
    def has_error(self) -> bool:
        """Check if there is an error."""
        return bool(st.session_state.error)
    
    def get_error(self) -> Optional[str]:
        """Get the current error message."""
        return st.session_state.error
    
    def clear_error(self) -> None:
        """Clear the current error."""
        st.session_state.error = None