"""
Metadata Manager Modul.
Verantwortlich für die Verwaltung und Verarbeitung von Dokumenten-Metadaten.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
import re
from collections import defaultdict

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

class MetadataManagerError(ServiceError):
    """Spezifische Exception für Metadaten-Manager-Fehler."""
    pass

class MetadataManager:
    """
    Manager für Dokumenten-Metadaten.
    
    Features:
    - Metadaten-Extraktion und -Validierung
    - Themen- und Schlüsselwort-Erkennung
    - Metadaten-Normalisierung
    - Statistiken und Aggregationen
    """
    
    def __init__(self):
        """Initialisiert den Metadata-Manager."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        # Initialisiere Wörterbuch für Themenerkennung
        self._topic_keywords = {
            "sicherheit": [
                "sicherheit", "schutz", "airbag", "gurt", "crash", "unfall",
                "warnung", "prävention", "notfall", "rettung"
            ],
            "technik": [
                "motor", "getriebe", "antrieb", "elektronik", "steuerung",
                "sensor", "system", "diagnose", "komponente", "modul"
            ],
            "wartung": [
                "wartung", "service", "inspektion", "reparatur", "pflege",
                "check", "prüfung", "intervall", "werkstatt", "austausch"
            ],
            "umwelt": [
                "emission", "verbrauch", "co2", "umwelt", "katalysator",
                "filter", "grenzwert", "abgas", "effizienz", "green"
            ],
            "recht": [
                "gesetz", "verordnung", "vorschrift", "regelung", "paragraph",
                "bestimmung", "richtlinie", "zulassung", "pflicht", "norm"
            ]
        }
    
    @log_function_call(logger)
    async def extract_metadata(self, content: str) -> Dict[str, Any]:
        """
        Extrahiert Metadaten aus dem Dokumenteninhalt.
        
        Args:
            content: Dokumenteninhalt
            
        Returns:
            Dictionary mit extrahierten Metadaten
        """
        try:
            with log_execution_time(self.logger, "metadata_extraction"):
                metadata = {
                    "extracted_at": datetime.utcnow().isoformat(),
                    "content_length": len(content),
                    "language": await self._detect_language(content),
                    "topics": await self._extract_topics(content),
                    "keywords": await self._extract_keywords(content),
                    "complexity_score": await self._calculate_complexity(content)
                }
                
                self.logger.debug(
                    "Metadaten extrahiert",
                    extra={
                        "metadata_keys": list(metadata.keys()),
                        "topics_count": len(metadata["topics"])
                    }
                )
                return metadata
                
        except Exception as e:
            error_context = {"content_length": len(content)}
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Metadaten-Extraktion"
            )
            raise MetadataManagerError(f"Metadaten-Extraktion fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def merge_metadata(
        self,
        base_metadata: Dict[str, Any],
        new_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Führt zwei Metadaten-Dictionaries zusammen.
        
        Args:
            base_metadata: Basis-Metadaten
            new_metadata: Neue Metadaten
            
        Returns:
            Zusammengeführte Metadaten
        """
        try:
            merged = base_metadata.copy()
            
            # Listen zusammenführen und Duplikate entfernen
            for key in ["topics", "keywords"]:
                if key in new_metadata:
                    existing = set(merged.get(key, []))
                    new_items = set(new_metadata[key])
                    merged[key] = list(existing | new_items)
            
            # Numerische Werte aktualisieren
            for key in ["complexity_score", "importance_score"]:
                if key in new_metadata:
                    merged[key] = new_metadata[key]
            
            # Zeitstempel aktualisieren
            merged["updated_at"] = datetime.utcnow().isoformat()
            
            self.logger.debug(
                "Metadaten zusammengeführt",
                extra={
                    "base_keys": list(base_metadata.keys()),
                    "new_keys": list(new_metadata.keys()),
                    "merged_keys": list(merged.keys())
                }
            )
            return merged
            
        except Exception as e:
            error_context = {
                "base_keys": list(base_metadata.keys()),
                "new_keys": list(new_metadata.keys())
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Zusammenführen von Metadaten"
            )
            raise MetadataManagerError(
                f"Metadaten-Zusammenführung fehlgeschlagen: {str(e)}"
            )
    
    async def _detect_language(self, content: str) -> str:
        """
        Erkennt die Sprache des Inhalts.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Erkannter Sprachcode
        """
        # Vereinfachte Implementierung - sollte in Produktion durch
        # eine richtige Spracherkennungsbibliothek ersetzt werden
        german_indicators = [
            "der", "die", "das", "und", "ist", "sind", "werden",
            "fahrzeug", "prüfung", "vorschrift"
        ]
        text_lower = content.lower()
        german_word_count = sum(1 for word in german_indicators if word in text_lower)
        return "de" if german_word_count >= 3 else "en"
    
    async def _extract_topics(self, content: str) -> List[str]:
        """
        Extrahiert relevante Themen aus dem Inhalt.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Liste erkannter Themen
        """
        content_lower = content.lower()
        found_topics = []
        
        # Themen basierend auf Schlüsselwörtern erkennen
        for topic, keywords in self._topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                found_topics.append(topic)
        
        return found_topics
    
    async def _extract_keywords(self, content: str) -> List[str]:
        """
        Extrahiert wichtige Schlüsselwörter.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Liste wichtiger Schlüsselwörter
        """
        # Wörter extrahieren und normalisieren
        words = re.findall(r'\b\w+\b', content.lower())
        
        # Stopwörter filtern (vereinfachte Liste)
        stopwords = {
            "der", "die", "das", "und", "in", "im", "für", "mit",
            "bei", "seit", "von", "aus", "nach", "zu", "zur", "zum"
        }
        filtered_words = [w for w in words if w not in stopwords]
        
        # Worthäufigkeiten zählen
        word_freq = defaultdict(int)
        for word in filtered_words:
            word_freq[word] += 1
        
        # Top-Keywords basierend auf Häufigkeit
        keywords = sorted(
            word_freq.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return [word for word, _ in keywords]
    
    async def _calculate_complexity(self, content: str) -> float:
        """
        Berechnet einen Komplexitätsscore für den Inhalt.
        
        Args:
            content: Zu analysierender Text
            
        Returns:
            Komplexitätsscore zwischen 0 und 1
        """
        try:
            # Verschiedene Faktoren für Komplexität
            factors = {
                "sentence_length": self._avg_sentence_length(content),
                "word_length": self._avg_word_length(content),
                "special_terms": self._count_special_terms(content),
            }
            
            # Gewichtete Summe der Faktoren
            weights = {"sentence_length": 0.4, "word_length": 0.3, "special_terms": 0.3}
            complexity = sum(
                factor * weights[name]
                for name, factor in factors.items()
            )
            
            # Auf 0-1 normalisieren
            return min(max(complexity / 10, 0), 1)
            
        except Exception:
            return 0.5  # Fallback bei Fehler
    
    def _avg_sentence_length(self, text: str) -> float:
        """Berechnet durchschnittliche Satzlänge."""
        sentences = re.split(r'[.!?]+', text)
        if not sentences:
            return 0
        return sum(len(s.split()) for s in sentences) / len(sentences)
    
    def _avg_word_length(self, text: str) -> float:
        """Berechnet durchschnittliche Wortlänge."""
        words = re.findall(r'\b\w+\b', text)
        if not words:
            return 0
        return sum(len(word) for word in words) / len(words)
    
    def _count_special_terms(self, text: str) -> int:
        """Zählt Fachbegriffe im Text."""
        technical_terms = {
            "abs", "esp", "asv", "tcs", "egr", "dpf", "scr", "obd",
            "ecu", "can", "lin", "iso", "sae", "din", "ece", "etk"
        }
        return sum(1 for term in technical_terms if term.lower() in text.lower())
    
    @log_function_call(logger)
    async def validate_metadata(
        self,
        metadata: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validiert Metadaten auf Vollständigkeit und Korrektheit.
        
        Args:
            metadata: Zu validierende Metadaten
            
        Returns:
            Tuple aus (is_valid, error_message)
        """
        try:
            # Pflichtfelder prüfen
            required_fields = [
                "created_at",
                "content_length",
                "language"
            ]
            
            for field in required_fields:
                if field not in metadata:
                    return False, f"Pflichtfeld fehlt: {field}"
            
            # Typ-Validierung
            type_checks = {
                "created_at": str,
                "content_length": int,
                "language": str,
                "topics": list,
                "keywords": list
            }
            
            for field, expected_type in type_checks.items():
                if field in metadata and not isinstance(
                    metadata[field],
                    expected_type
                ):
                    return False, f"Ungültiger Typ für {field}"
            
            # Wertebereiche prüfen
            if "complexity_score" in metadata:
                score = metadata["complexity_score"]
                if not isinstance(score, (int, float)) or not 0 <= score <= 1:
                    return False, "Ungültiger complexity_score"
            
            return True, None
            
        except Exception as e:
            self.logger.error(f"Fehler bei Metadaten-Validierung: {str(e)}")
            return False, f"Validierungsfehler: {str(e)}"