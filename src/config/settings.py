from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from pathlib import Path

class LoggingSettings(BaseModel):
    """
    Einstellungen für das Logging-System.
    Definiert alle logging-spezifischen Konfigurationsoptionen.
    """
    # Basis-Einstellungen
    log_dir: str = Field(
        default="logs",
        description="Verzeichnis für Log-Dateien"
    )
    log_level: str = Field(
        default="INFO",
        description="Standard Log-Level"
    )
    debug_mode: bool = Field(
        default=False,
        description="Debug-Modus aktivieren"
    )
    
    # Performance-Logging
    enable_performance_logging: bool = Field(
        default=True,
        description="Performance-Logging aktivieren"
    )
    
    # Log-Rotation
    max_file_size: int = Field(
        default=10485760,  # 10MB
        description="Maximale Größe einer Log-Datei"
    )
    backup_count: int = Field(
        default=5,
        description="Anzahl der Backup-Dateien bei Rotation"
    )
    
    # Log-Formate
    include_request_id: bool = Field(
        default=True,
        description="Request-IDs in Logs einbinden"
    )

class SecuritySettings(BaseModel):
    """
    Sicherheitsrelevante Einstellungen.
    Konfiguriert Authentifizierung, Autorisierung und andere Sicherheitsaspekte.
    """
    enable_auth: bool = Field(
        default=True,
        description="Authentifizierung aktivieren"
    )
    session_lifetime: int = Field(
        default=3600,  # 1 Stunde
        description="Session-Lebensdauer in Sekunden"
    )
    min_password_length: int = Field(
        default=8,
        description="Minimale Passwortlänge"
    )
    allowed_origins: list[str] = Field(
        default=["http://localhost:8501"],
        description="Erlaubte CORS Origins"
    )

class DatabaseSettings(BaseModel):
    """
    Datenbank-Konfiguration.
    Einstellungen für ChromaDB und andere Datenquellen.
    """
    persist_directory: str = Field(
        default="./data/chromadb",
        description="ChromaDB Persistenz-Verzeichnis"
    )
    collection_name: str = Field(
        default="documents",
        description="Name der ChromaDB Collection"
    )
    embedding_dimension: int = Field(
        default=384,
        description="Dimension der Dokument-Embeddings"
    )
    
    @validator('persist_directory')
    def create_persist_directory(cls, v):
        """Stellt sicher, dass das Persistenz-Verzeichnis existiert."""
        Path(v).mkdir(parents=True, exist_ok=True)
        return v

class ChatSettings(BaseModel):
    """
    Chat-System Konfiguration.
    Einstellungen für das Chat-Interface und die Verarbeitung.
    """
    max_context_messages: int = Field(
        default=10,
        description="Maximale Anzahl der Kontext-Nachrichten"
    )
    max_context_length: int = Field(  # Diese Zeile hinzufügen
        default=4000,
        description="Maximale Länge des Dokumenten-Kontexts in Zeichen"
    )
    system_prompt: str = Field(
        default="""Du bist ein Fahrzeug-Experten-Assistent der Motorfahrzeugkontrolle des Kantons Solothurn (Schweiz).
        Beantworte Fragen präzise, professionell und in natürlicher Sprache.
        Verwende korrekte Fachbegriffe und beziehe dich auf den Schweizer Kontext.
        Spreche in vollständigen, zusammenhängenden Sätzen ohne unnatürliche Pausen oder Lücken.""",
        description="System-Prompt für den Chat"
    )
    max_tokens: int = Field(
        default=2048,
        description="Maximale Token-Anzahl pro Antwort"
    )
    temperature: float = Field(
        default=0.1,
        description="Kreativität der Antworten (0.0-1.0)"
    )
    stream_response: bool = Field(
        default=True,
        description="Streaming-Antworten aktivieren"
    )
    min_input_delay: float = Field(
        default=1.0,
        description="Minimale Wartezeit zwischen Eingaben in Sekunden"
    )
class APISettings(BaseModel):
    """
    API-Konfiguration.
    Einstellungen für externe Services und APIs.
    """
    openai_model: str = Field(
        default="gpt-3.5-turbo",
        description="Zu verwendendes OpenAI Modell"
    )
    openai_timeout: int = Field(
        default=30,
        description="Timeout für OpenAI API Calls in Sekunden"
    )
    max_retries: int = Field(
        default=3,
        description="Maximale Anzahl von API Retry-Versuchen"
    )

class Settings(BaseSettings):
    """
    Haupt-Konfigurationsklasse der Anwendung.
    Zentrale Verwaltung aller Einstellungen.
    """
    # Erforderliche Einstellungen
    openai_api_key: str = Field(
        description="OpenAI API Schlüssel",
        alias="OPENAI_API_KEY"
    )
    
    # Umgebungseinstellungen
    environment: str = Field(
        default="development",
        description="Ausführungsumgebung (development/staging/production)"
    )
    debug: bool = Field(
        default=False,
        description="Debug-Modus für die Anwendung"
    )
    
    # Komponenten-Einstellungen
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Logging-Einstellungen"
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Sicherheitseinstellungen"
    )
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Datenbank-Einstellungen"
    )
    chat: ChatSettings = Field(
        default_factory=ChatSettings,
        description="Chat-Einstellungen"
    )
    api: APISettings = Field(
        default_factory=APISettings,
        description="API-Einstellungen"
    )
    
    class Config:
        """Konfiguration für das Settings-Modell."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False
    
    def get_environment_vars(self) -> Dict[str, Any]:
        """
        Gibt alle Umgebungsvariablen zurück, die für die Konfiguration
        relevant sind.
        """
        return {
            "ENVIRONMENT": self.environment,
            "DEBUG": self.debug,
            "LOG_LEVEL": self.logging.log_level,
            "OPENAI_API_KEY": self.openai_api_key,
        }

# Globale Instanz der Settings
settings = Settings()

# Hilfsfunktion zum Abrufen der Settings
def get_settings() -> Settings:
    """
    Getter-Funktion für die Anwendungseinstellungen.
    
    Returns:
        Settings: Konfigurierte Settings-Instanz
    
    Beispiel:
        settings = get_settings()
        log_level = settings.logging.log_level
    """
    return settings