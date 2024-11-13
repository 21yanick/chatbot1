# src/backend/config/settings.py

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class DatabaseSettings(BaseSettings):
    """Database configuration settings."""
    
    persist_directory: str = Field(
        default="./data/chromadb",
        description="Directory for ChromaDB persistence"
    )
    collection_name: str = Field(
        default="documents",
        description="Name of the ChromaDB collection"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Dimension of document embeddings"
    )

class ChatSettings(BaseSettings):
    """Chat-related configuration settings."""
    
    max_context_length: int = Field(
        default=2048,
        description="Maximum context length in tokens"
    )
    max_context_messages: int = Field(
        default=10,
        description="Maximum number of messages to include in context"
    )
    system_prompt: str = Field(
        default="You are a helpful vehicle expert assistant.",
        description="Default system prompt"
    )

class Settings(BaseSettings):
    """Main application settings."""
    
    # Basis-Einstellungen
    environment: str = Field(
        default="development",
        description="Application environment"
    )
    debug: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    
    # API Keys und externe Services
    openai_api_key: str = Field(
        description="OpenAI API Key",
        alias="OPENAI_API_KEY"
    )
    
    # Logging und Debug
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Datenbank-Einstellungen
    chromadb_persist_directory: str = Field(
        default="./data/chromadb",
        description="ChromaDB persistence directory"
    )
    
    # Verschachtelte Einstellungen
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database settings"
    )
    chat: ChatSettings = Field(
        default_factory=ChatSettings,
        description="Chat settings"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False

# Create global settings instance
settings = Settings()