"""
Embedding-Service-Modul.
Verantwortlich für die Generierung und Verwaltung von Text-Embeddings mittels OpenAI.
"""

from typing import List, Dict, Any, Optional
import asyncio
from functools import lru_cache
import numpy as np
from langchain_openai import OpenAIEmbeddings

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..interfaces.base import BaseService, ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class EmbeddingCache:
    """
    Cache-Implementierung für Embeddings.
    
    Bietet Thread-sicheres Caching von Embedding-Vektoren zur 
    Vermeidung redundanter API-Aufrufe.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialisiert den Embedding-Cache.
        
        Args:
            max_size: Maximale Anzahl der zu cachenden Embeddings
        """
        self.cache: Dict[str, List[float]] = {}
        self.max_size = max_size
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.EmbeddingCache")

    async def get(self, key: str) -> Optional[List[float]]:
        """
        Ruft ein Embedding aus dem Cache ab.
        
        Args:
            key: Cache-Schlüssel (normalerweise der Text)
            
        Returns:
            Gecachter Embedding-Vektor oder None wenn nicht gefunden
        """
        async with self._lock:
            if embedding := self.cache.get(key):
                self.logger.debug(
                    "Cache-Treffer",
                    extra={"key_length": len(key)}
                )
                return embedding
            
            self.logger.debug(
                "Cache-Miss",
                extra={"key_length": len(key)}
            )
            return None

    async def set(self, key: str, value: List[float]) -> None:
        """
        Speichert ein Embedding im Cache.
        
        Args:
            key: Cache-Schlüssel
            value: Zu cachender Embedding-Vektor
        """
        async with self._lock:
            if len(self.cache) >= self.max_size:
                # Ältesten Eintrag entfernen wenn Cache voll
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.logger.debug(
                    "Cache-Eintrag entfernt",
                    extra={"removed_key_length": len(oldest_key)}
                )
            
            self.cache[key] = value
            self.logger.debug(
                "Cache-Eintrag hinzugefügt",
                extra={
                    "cache_size": len(self.cache),
                    "key_length": len(key)
                }
            )

    def clear(self) -> None:
        """Leert den Cache."""
        self.logger.info(
            "Cache geleert",
            extra={"cleared_entries": len(self.cache)}
        )
        self.cache.clear()

class EmbeddingServiceError(ServiceError):
    """Spezifische Exception für Embedding-Service-Fehler."""
    pass

class EmbeddingService(BaseService):
    """
    Service für die Generierung und Verwaltung von Embeddings.
    
    Verwendet OpenAI Embeddings mit integriertem Caching und
    Fehlerbehandlung für robuste Vektorisierung von Texten.
    """
    
    def __init__(
        self,
        model: str = "text-embedding-ada-002",
        batch_size: int = 100,
        cache_size: int = 10000,
        embeddings = None
    ):
        """
        Initialisiert den Embedding-Service.
        
        Args:
            model: Name des OpenAI Embedding-Modells
            batch_size: Maximale Batch-Größe für API-Anfragen
            cache_size: Größe des Embedding-Caches
            embeddings: Optionales vorkonfiguriertes Embedding-Modell
        """
        self.model = model
        self.batch_size = batch_size
        self._embeddings = embeddings
        self._cache = EmbeddingCache(max_size=cache_size)
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert den Embedding-Service.
        
        Raises:
            EmbeddingServiceError: Bei Initialisierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "embedding_initialization"):
                if not self._embeddings:
                    self._embeddings = OpenAIEmbeddings(
                        model=self.model
                    )
                    
            self.logger.info(
                "Embedding-Service initialisiert",
                extra={
                    "model": self.model,
                    "batch_size": self.batch_size
                }
            )
            
        except Exception as e:
            error_context = {
                "model": self.model
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Embedding-Service-Initialisierung"
            )
            raise EmbeddingServiceError(f"Initialisierung fehlgeschlagen: {str(e)}")
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Service-Ressourcen."""
        self._embeddings = None
        self._cache.clear()
        self.logger.info("Embedding-Service-Ressourcen bereinigt")

    @log_function_call(logger)
    async def get_embeddings(
        self,
        texts: List[str],
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ) -> List[List[float]]:
        """
        Generiert Embeddings für eine Liste von Texten mit Retry-Logik.
        
        Args:
            texts: Liste der zu verarbeitenden Texte
            retry_attempts: Maximale Anzahl von Wiederholungsversuchen
            retry_delay: Verzögerung zwischen Wiederholungsversuchen in Sekunden
            
        Returns:
            Liste von Embedding-Vektoren
            
        Raises:
            EmbeddingServiceError: Bei Fehlern in der Embedding-Generierung
        """
        if not self._embeddings:
            raise EmbeddingServiceError("Embedding-Service nicht initialisiert")
        
        async with self._lock:
            try:
                with log_execution_time(self.logger, "batch_embedding_generation"):
                    # Cache-Check
                    cached_results = []
                    missing_indices = []
                    
                    for i, text in enumerate(texts):
                        if cached := await self._cache.get(text):
                            cached_results.append(cached)
                        else:
                            cached_results.append(None)
                            missing_indices.append(i)
                    
                    if not missing_indices:
                        self.logger.info(
                            "Alle Embeddings im Cache gefunden",
                            extra={"total_texts": len(texts)}
                        )
                        return [r for r in cached_results if r is not None]
                    
                    # Fehlende Embeddings in Batches verarbeiten
                    missing_texts = [texts[i] for i in missing_indices]
                    all_embeddings = []
                    
                    for i in range(0, len(missing_texts), self.batch_size):
                        batch = missing_texts[i:i + self.batch_size]
                        
                        for attempt in range(retry_attempts):
                            try:
                                with log_execution_time(self.logger, "api_call"):
                                    batch_embeddings = self._embeddings.embed_documents(batch)
                                    
                                all_embeddings.extend(batch_embeddings)
                                break
                                
                            except Exception as e:
                                if attempt == retry_attempts - 1:
                                    raise EmbeddingServiceError(
                                        f"Embedding-Generierung nach {retry_attempts} "
                                        f"Versuchen fehlgeschlagen: {str(e)}"
                                    )
                                    
                                self.logger.warning(
                                    f"Embedding-Versuch {attempt + 1} fehlgeschlagen",
                                    extra={
                                        "attempt": attempt + 1,
                                        "max_attempts": retry_attempts,
                                        "batch_size": len(batch)
                                    }
                                )
                                await asyncio.sleep(retry_delay * (attempt + 1))
                    
                    # Cache aktualisieren und Ergebnisse zusammenführen
                    for i, embedding in zip(missing_indices, all_embeddings):
                        await self._cache.set(texts[i], embedding)
                        cached_results[i] = embedding
                    
                    self.logger.info(
                        "Embeddings generiert",
                        extra={
                            "total_texts": len(texts),
                            "cache_hits": len(texts) - len(missing_indices),
                            "newly_generated": len(missing_indices)
                        }
                    )
                    
                    return [r for r in cached_results if r is not None]
                
            except Exception as e:
                error_context = {
                    "total_texts": len(texts),
                    "batch_size": self.batch_size
                }
                log_error_with_context(
                    self.logger,
                    e,
                    error_context,
                    "Fehler bei Embedding-Generierung"
                )
                raise EmbeddingServiceError(f"Embedding-Generierung fehlgeschlagen: {str(e)}")

    @log_function_call(logger)
    async def get_embedding(
        self,
        text: str,
        retry_attempts: int = 3
    ) -> List[float]:
        """
        Generiert ein Embedding für einen einzelnen Text.
        
        Args:
            text: Zu verarbeitender Text
            retry_attempts: Maximale Anzahl von Wiederholungsversuchen
            
        Returns:
            Embedding-Vektor
            
        Raises:
            EmbeddingServiceError: Bei Fehlern in der Embedding-Generierung
        """
        embeddings = await self.get_embeddings([text], retry_attempts)
        return embeddings[0]
    
    @log_function_call(logger)
    def similarity_score(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Berechnet die Kosinus-Ähnlichkeit zwischen zwei Embeddings.
        
        Args:
            embedding1: Erster Embedding-Vektor
            embedding2: Zweiter Embedding-Vektor
            
        Returns:
            Ähnlichkeitswert zwischen 0 und 1
            
        Raises:
            EmbeddingServiceError: Bei Berechnungsfehlern
        """
        try:
            with log_execution_time(self.logger, "similarity_calculation"):
                a = np.array(embedding1)
                b = np.array(embedding2)
                similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                
                self.logger.debug(
                    "Ähnlichkeit berechnet",
                    extra={"similarity_score": similarity}
                )
                return similarity
                
        except Exception as e:
            error_context = {
                "vector1_size": len(embedding1),
                "vector2_size": len(embedding2)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Ähnlichkeitsberechnung"
            )
            raise EmbeddingServiceError(
                f"Ähnlichkeitsberechnung fehlgeschlagen: {str(e)}"
            )