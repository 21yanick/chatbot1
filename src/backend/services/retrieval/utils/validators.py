"""
Validierungs-Modul für Dokumente.
Stellt Validierungslogik für Dokumente und verwandte Datenstrukturen bereit.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import re
from urllib.parse import urlparse

from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    log_function_call
)
from src.backend.models.document import Document, DocumentType, DocumentStatus
from src.backend.interfaces.base import ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class ValidationError(ServiceError):
    """Spezifische Exception für Validierungsfehler."""
    pass

class DocumentValidator:
    """
    Validator für Dokumente und deren Komponenten.
    
    Features:
    - Vollständige Dokumentvalidierung
    - Metadaten-Validierung
    - URL-Validierung
    - Inhaltsvalidierung
    - Format- und Typprüfungen
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialisiert den Document Validator.
        
        Args:
            strict_mode: Ob strikte Validierung aktiviert werden soll
        """
        self.strict_mode = strict_mode
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        # Minimale und maximale Längen
        self.MIN_TITLE_LENGTH = 3
        self.MAX_TITLE_LENGTH = 200
        self.MIN_CONTENT_LENGTH = 10
        self.MAX_CONTENT_LENGTH = 1_000_000  # 1MB
        
        # Regex-Patterns
        self.VALID_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
        self.VALID_LANGUAGE_PATTERN = re.compile(r'^[a-z]{2}(-[A-Z]{2})?$')
    
    @log_function_call(logger)
    async def validate(self, document: Document) -> bool:
        """
        Führt eine vollständige Validierung eines Dokuments durch.
        
        Args:
            document: Zu validierendes Dokument
            
        Returns:
            True wenn Dokument gültig
            
        Note:
            Loggt Validierungsfehler aber wirft keine Exceptions
        """
        try:
            with log_execution_time(self.logger, "document_validation"):
                # Basis-Validierungen
                validations = [
                    self._validate_id(document.id),
                    self._validate_title(document.title),
                    self._validate_content(document.content),
                    self._validate_source_link(document.source_link),
                    await self._validate_metadata(document.metadata),
                    self._validate_language(document.language),
                    self._validate_status(document.status)
                ]
                
                # Zusätzliche strikte Validierungen
                if self.strict_mode:
                    validations.extend([
                        self._validate_topics(document.topics),
                        self._validate_scores(document)
                    ])
                
                # Alle Validierungen prüfen
                is_valid = all(validations)
                
                self.logger.info(
                    f"Dokument {'erfolgreich' if is_valid else 'nicht'} validiert",
                    extra={
                        "document_id": document.id,
                        "strict_mode": self.strict_mode,
                        "valid": is_valid
                    }
                )
                
                return is_valid
                
        except Exception as e:
            self.logger.error(
                f"Fehler bei Dokumentvalidierung: {str(e)}",
                extra={"document_id": document.id}
            )
            return False
    
    def _validate_id(self, doc_id: str) -> bool:
        """Validiert eine Dokument-ID."""
        if not doc_id or not isinstance(doc_id, str):
            self.logger.warning("Ungültige Dokument-ID: None oder falscher Typ")
            return False
            
        if not self.VALID_ID_PATTERN.match(doc_id):
            self.logger.warning(
                "Ungültige Dokument-ID: Ungültiges Format",
                extra={"id": doc_id}
            )
            return False
            
        return True
    
    def _validate_title(self, title: str) -> bool:
        """Validiert einen Dokumenttitel."""
        if not title or not isinstance(title, str):
            self.logger.warning("Ungültiger Titel: None oder falscher Typ")
            return False
            
        if not self.MIN_TITLE_LENGTH <= len(title) <= self.MAX_TITLE_LENGTH:
            self.logger.warning(
                "Ungültiger Titel: Länge außerhalb der Grenzen",
                extra={"title_length": len(title)}
            )
            return False
            
        return True
    
    def _validate_content(self, content: str) -> bool:
        """Validiert Dokumentinhalt."""
        if not content or not isinstance(content, str):
            self.logger.warning("Ungültiger Inhalt: None oder falscher Typ")
            return False
            
        if not self.MIN_CONTENT_LENGTH <= len(content) <= self.MAX_CONTENT_LENGTH:
            self.logger.warning(
                "Ungültiger Inhalt: Länge außerhalb der Grenzen",
                extra={"content_length": len(content)}
            )
            return False
            
        return True
    
    def _validate_source_link(self, url: str) -> bool:
        """Validiert einen Source-Link."""
        if not url or not isinstance(url, str):
            self.logger.warning("Ungültiger Source-Link: None oder falscher Typ")
            return False
            
        try:
            result = urlparse(url)
            is_valid = all([result.scheme, result.netloc])
            if not is_valid:
                self.logger.warning(
                    "Ungültiger Source-Link: Ungültiges URL-Format",
                    extra={"url": url}
                )
            return is_valid
        except Exception as e:
            self.logger.warning(
                f"Fehler bei URL-Validierung: {str(e)}",
                extra={"url": url}
            )
            return False
    
    async def _validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validiert Dokument-Metadaten.
        
        Prüft:
        - Typ und Struktur
        - Pflichtfelder
        - Feldtypen und -formate
        """
        if not isinstance(metadata, dict):
            self.logger.warning("Ungültige Metadaten: Kein Dictionary")
            return False
            
        # Pflichtfelder prüfen
        required_fields = ["created_at"]
        for field in required_fields:
            if field not in metadata:
                self.logger.warning(
                    f"Pflichtfeld fehlt in Metadaten: {field}"
                )
                return False
        
        # Datumsformat prüfen
        try:
            datetime.fromisoformat(metadata["created_at"])
        except (ValueError, TypeError):
            self.logger.warning(
                "Ungültiges Datumsformat in Metadaten",
                extra={"created_at": metadata.get("created_at")}
            )
            return False
        
        return True
    
    def _validate_language(self, language: str) -> bool:
        """Validiert einen Sprachcode."""
        if not language or not isinstance(language, str):
            self.logger.warning("Ungültiger Sprachcode: None oder falscher Typ")
            return False
            
        if not self.VALID_LANGUAGE_PATTERN.match(language):
            self.logger.warning(
                "Ungültiger Sprachcode: Falsches Format",
                extra={"language": language}
            )
            return False
            
        return True
    
    def _validate_status(self, status: DocumentStatus) -> bool:
        """Validiert einen Dokumentstatus."""
        try:
            if not isinstance(status, DocumentStatus):
                self.logger.warning(
                    "Ungültiger Status: Kein DocumentStatus-Enum",
                    extra={"status": status}
                )
                return False
            return True
        except Exception:
            return False
    
    def _validate_topics(self, topics: list) -> bool:
        """Validiert Dokument-Topics."""
        if not isinstance(topics, list):
            self.logger.warning("Ungültige Topics: Keine Liste")
            return False
            
        # Einzelne Topics validieren
        for topic in topics:
            if not isinstance(topic, str):
                self.logger.warning(
                    "Ungültiges Topic: Kein String",
                    extra={"topic": topic}
                )
                return False
                
            if not 2 <= len(topic) <= 50:
                self.logger.warning(
                    "Ungültige Topic-Länge",
                    extra={"topic": topic, "length": len(topic)}
                )
                return False
        
        return True
    
    def _validate_scores(self, document: Document) -> bool:
        """Validiert Dokument-Scores."""
        try:
            # Importance Score prüfen
            if not 0 <= document.importance_score <= 1:
                self.logger.warning(
                    "Ungültiger Importance-Score",
                    extra={"score": document.importance_score}
                )
                return False
            
            # Validation Score prüfen
            if not 0 <= document.validation_score <= 1:
                self.logger.warning(
                    "Ungültiger Validation-Score",
                    extra={"score": document.validation_score}
                )
                return False
            
            return True
        except Exception:
            return False

class MetadataValidator:
    """
    Spezialisierter Validator für Metadaten-Strukturen.
    
    Bietet detaillierte Validierung für:
    - Metadaten-Formate
    - Feldtypen und -werte
    - Beziehungen zwischen Feldern
    """
    
    def __init__(self):
        """Initialisiert den Metadata Validator."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def validate(
        self,
        metadata: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validiert eine Metadaten-Struktur.
        
        Args:
            metadata: Zu validierende Metadaten
            
        Returns:
            Tuple aus (is_valid, error_message)
        """
        try:
            # Basisstruktur prüfen
            if not isinstance(metadata, dict):
                return False, "Metadaten müssen ein Dictionary sein"
            
            # Pflichtfelder prüfen
            required_fields = ["created_at"]
            for field in required_fields:
                if field not in metadata:
                    return False, f"Pflichtfeld fehlt: {field}"
            
            # Feldtypen prüfen
            type_validations = {
                "created_at": (str, self._validate_iso_date),
                "content_length": (int, lambda x: x >= 0),
                "language": (str, lambda x: len(x) == 2),
                "topics": (list, lambda x: all(isinstance(t, str) for t in x)),
                "importance_score": (float, lambda x: 0 <= x <= 1),
                "validation_score": (float, lambda x: 0 <= x <= 1)
            }
            
            for field, (expected_type, validator) in type_validations.items():
                if field in metadata:
                    value = metadata[field]
                    if not isinstance(value, expected_type):
                        return False, f"Ungültiger Typ für {field}"
                    if not validator(value):
                        return False, f"Ungültiger Wert für {field}"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Fehler bei Metadaten-Validierung: {str(e)}")
            return False, f"Validierungsfehler: {str(e)}"
    
    def _validate_iso_date(self, date_str: str) -> bool:
        """Validiert ein ISO-Datums-Format."""
        try:
            datetime.fromisoformat(date_str)
            return True
        except (ValueError, TypeError):
            return False