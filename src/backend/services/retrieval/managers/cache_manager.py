"""
Cache Manager Modul.
Verantwortlich für das Caching von Dokumenten mit Thread-Sicherheit und Konfigurierbarkeit.
"""

from typing import Optional, Dict, Any
import asyncio
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

from src.config.settings import settings
from src.config.logging_config import (
    get_logger,
    log_execution_time,
    log_error_with_context,
    log_function_call
)
from src.backend.models.document import Document
from src.backend.interfaces.base import ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class CacheManagerError(ServiceError):
    """Spezifische Exception für Cache-Manager-Fehler."""
    pass

class CacheEntry:
    """Repräsentiert einen einzelnen Cache-Eintrag mit Metadaten."""
    
    def __init__(self, document: Document, ttl: Optional[int] = None):
        """
        Initialisiert einen Cache-Eintrag.
        
        Args:
            document: Zu cachendes Dokument
            ttl: Time-to-live in Sekunden (Optional)
        """
        self.document = document
        self.created_at = datetime.utcnow()
        self.last_accessed = self.created_at
        self.access_count = 0
        self.ttl = ttl
        
    def is_expired(self) -> bool:
        """Prüft ob der Cache-Eintrag abgelaufen ist."""
        if self.ttl is None:
            return False
        return datetime.utcnow() > self.created_at + timedelta(seconds=self.ttl)
    
    def access(self) -> None:
        """Aktualisiert Zugriffsinformationen."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

class CacheManager:
    """
    Manager für dokumentbasiertes Caching.
    
    Features:
    - Thread-sichere Implementierung
    - LRU (Least Recently Used) Ersetzungsstrategie
    - TTL (Time-To-Live) Unterstützung
    - Automatische Cache-Bereinigung
    - Statistiken und Monitoring
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[int] = 3600,
        cleanup_interval: int = 300
    ):
        """
        Initialisiert den Cache-Manager.
        
        Args:
            max_size: Maximale Anzahl von Cache-Einträgen
            default_ttl: Standard-TTL in Sekunden (None für unbegrenzt)
            cleanup_interval: Intervall für Cache-Bereinigung in Sekunden
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0
        }
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        # Cleanup-Task starten
        if cleanup_interval > 0:
            self._start_cleanup_task()
    
    def _start_cleanup_task(self) -> None:
        """Startet den automatischen Cleanup-Task."""
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup()
        
        asyncio.create_task(cleanup_loop())
        self.logger.debug(
            "Cleanup-Task gestartet",
            extra={"interval": self._cleanup_interval}
        )
    
    @log_function_call(logger)
    async def get(self, document_id: str) -> Optional[Document]:
        """
        Ruft ein Dokument aus dem Cache ab.
        
        Args:
            document_id: ID des gewünschten Dokuments
            
        Returns:
            Gecachtes Dokument oder None wenn nicht gefunden
        """
        try:
            with self._lock:
                if document_id in self._cache:
                    entry = self._cache[document_id]
                    
                    # Prüfen ob Eintrag abgelaufen ist
                    if entry.is_expired():
                        self._remove_entry(document_id)
                        self._stats["misses"] += 1
                        return None
                    
                    # LRU-Update und Zugriffszähler
                    self._cache.move_to_end(document_id)
                    entry.access()
                    self._stats["hits"] += 1
                    
                    self.logger.debug(
                        "Cache-Hit",
                        extra={
                            "document_id": document_id,
                            "access_count": entry.access_count
                        }
                    )
                    return entry.document
                
                self._stats["misses"] += 1
                self.logger.debug(
                    "Cache-Miss",
                    extra={"document_id": document_id}
                )
                return None
                
        except Exception as e:
            self.logger.error(
                f"Fehler bei Cache-Zugriff: {str(e)}",
                extra={"document_id": document_id}
            )
            return None
    
    @log_function_call(logger)
    async def put(
        self,
        document: Document,
        ttl: Optional[int] = None
    ) -> None:
        """
        Fügt ein Dokument zum Cache hinzu.
        
        Args:
            document: Zu cachendes Dokument
            ttl: Optionale TTL-Überschreibung
        """
        try:
            with self._lock:
                # Cache-Größe prüfen und ggf. LRU-Eintrag entfernen
                while len(self._cache) >= self._max_size:
                    self._remove_lru_entry()
                
                # Neuen Eintrag erstellen
                self._cache[document.id] = CacheEntry(
                    document,
                    ttl or self._default_ttl
                )
                self._cache.move_to_end(document.id)
                
                self.logger.debug(
                    "Dokument gecacht",
                    extra={
                        "document_id": document.id,
                        "ttl": ttl or self._default_ttl,
                        "cache_size": len(self._cache)
                    }
                )
                
        except Exception as e:
            self.logger.error(
                f"Fehler beim Caching: {str(e)}",
                extra={"document_id": document.id}
            )
    
    @log_function_call(logger)
    async def remove(self, document_id: str) -> bool:
        """
        Entfernt ein Dokument aus dem Cache.
        
        Args:
            document_id: ID des zu entfernenden Dokuments
            
        Returns:
            True wenn Dokument entfernt wurde
        """
        try:
            with self._lock:
                if document_id in self._cache:
                    self._remove_entry(document_id)
                    self.logger.debug(
                        "Dokument aus Cache entfernt",
                        extra={"document_id": document_id}
                    )
                    return True
                return False
                
        except Exception as e:
            self.logger.error(
                f"Fehler bei Cache-Entfernung: {str(e)}",
                extra={"document_id": document_id}
            )
            return False
    
    @log_function_call(logger)
    async def cleanup(self) -> int:
        """
        Bereinigt abgelaufene Cache-Einträge.
        
        Returns:
            Anzahl der entfernten Einträge
        """
        try:
            with self._lock:
                expired_keys = [
                    key for key, entry in self._cache.items()
                    if entry.is_expired()
                ]
                
                for key in expired_keys:
                    self._remove_entry(key)
                
                self._stats["cleanups"] += 1
                
                self.logger.info(
                    "Cache bereinigt",
                    extra={
                        "removed_count": len(expired_keys),
                        "remaining_size": len(self._cache)
                    }
                )
                
                return len(expired_keys)
                
        except Exception as e:
            self.logger.error(f"Fehler bei Cache-Bereinigung: {str(e)}")
            return 0
    
    def _remove_entry(self, key: str) -> None:
        """
        Entfernt einen Cache-Eintrag.
        
        Args:
            key: Schlüssel des zu entfernenden Eintrags
        """
        self._cache.pop(key, None)
        self._stats["evictions"] += 1
    
    def _remove_lru_entry(self) -> None:
        """Entfernt den am längsten nicht genutzten Eintrag."""
        if self._cache:
            lru_key = next(iter(self._cache))
            self._remove_entry(lru_key)
    
    @log_function_call(logger)
    async def get_stats(self) -> Dict[str, Any]:
        """
        Gibt Cache-Statistiken zurück.
        
        Returns:
            Dictionary mit Cache-Statistiken
        """
        with self._lock:
            stats = self._stats.copy()
            stats.update({
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_ratio": (
                    stats["hits"] / (stats["hits"] + stats["misses"])
                    if (stats["hits"] + stats["misses"]) > 0
                    else 0
                )
            })
            return stats
    
    @log_function_call(logger)
    async def clear(self) -> None:
        """Leert den Cache vollständig."""
        try:
            with self._lock:
                self._cache.clear()
                self._stats = {
                    "hits": 0,
                    "misses": 0,
                    "evictions": 0,
                    "cleanups": 0
                }
                
                self.logger.info("Cache geleert")
                
        except Exception as e:
            self.logger.error(f"Fehler beim Leeren des Cache: {str(e)}")
            
    def __len__(self) -> int:
        """Gibt die aktuelle Cache-Größe zurück."""
        with self._lock:
            return len(self._cache)