# src/backend/config/settings.py
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from typing import Optional

class ChatSettings(BaseModel):
    """Chat specific settings."""
    max_context_messages: int = 10
    system_prompt: str = "You are a helpful vehicle expert assistant."
    embedding_dimension: int = 384

class DatabaseSettings(BaseModel):
    """Database specific settings."""
    persist_directory: str = "./data/chromadb"
    collection_name: str = "documents"

class Settings(BaseSettings):
    """Application settings."""
    # Required settings
    openai_api_key: str
    
    # Optional settings
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Nested settings
    chat: ChatSettings = ChatSettings()
    database: DatabaseSettings = DatabaseSettings()
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = False