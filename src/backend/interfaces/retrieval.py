"""
Retrieval-Service-Interface-Modul.
Definiert die Schnittstelle für Dokumenten-Retrieval und -Management.
"""

from typing import List, Optional, Dict, Any
from abc import abstractmethod

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..models.document import Document
from .base import BaseService, ServiceError

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class RetrievalServiceError(ServiceError):
    """
    Spezifische Exception für Retrieval-Service-Fehler.
    
    Erweitert die Basis-ServiceError um retrieval-spezifische Fehlerbehandlung.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialisiert die RetrievalServiceError Exception.
        
        Args:
            message: Beschreibende Fehlermeldung
            details: Optionale zusätzliche Fehlerdetails
        """
        super().__init__(f"Retrieval-Service-Fehler: {message}", details)

class RetrievalService(BaseService):
    """
    Interface für Dokumenten-Retrieval-Operationen.
    
    Definiert die grundlegende Schnittstelle für:
    - Dokumentenverwaltung
    - Semantische Suche
    - Ähnlichkeitsanalyse
    - Metadaten-Filterung
    """
    
    def __init__(self):
        """Initialisiert den Retrieval-Service mit einem spezifischen Logger."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    @abstractmethod
    async def add_document(self, document: Document) -> Document:
        """
        Fügt ein Dokument zum Retrieval-System hinzu.
        
        Args:
            document: Hinzuzufügendes Dokument
            
        Returns:
            Verarbeitetes und gespeichertes Dokument
            
        Raises:
            RetrievalServiceError: Bei Fehlern beim Hinzufügen
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def get_document(self, document_id: str) -> Optional[Document]:
        """
        Ruft ein Dokument anhand seiner ID ab.
        
        Args:
            document_id: ID des gewünschten Dokuments
            
        Returns:
            Gefundenes Dokument oder None falls nicht gefunden
            
        Raises:
            RetrievalServiceError: Bei Abruffehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def search_documents(
        self,
        query: str,
        limit: int = 5,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Sucht nach Dokumenten basierend auf semantischer Ähnlichkeit.
        
        Args:
            query: Suchanfrage
            limit: Maximale Anzahl zurückzugebender Dokumente
            metadata_filter: Optionale Filter für Dokument-Metadaten
            
        Returns:
            Liste gefundener Dokumente, sortiert nach Relevanz
            
        Raises:
            RetrievalServiceError: Bei Suchfehlern
            
        Note:
            Die Suche verwendet Embedding-basierte semantische Ähnlichkeit
            und berücksichtigt dabei sowohl den Textinhalt als auch die
            Metadaten der Dokumente.
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """
        Löscht ein Dokument aus dem Retrieval-System.
        
        Args:
            document_id: ID des zu löschenden Dokuments
            
        Returns:
            True wenn erfolgreich gelöscht, False falls nicht gefunden
            
        Raises:
            RetrievalServiceError: Bei Löschfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def update_document(
        self,
        document_id: str,
        document: Document
    ) -> Optional[Document]:
        """
        Aktualisiert ein bestehendes Dokument.
        
        Args:
            document_id: ID des zu aktualisierenden Dokuments
            document: Neue Dokumentdaten
            
        Returns:
            Aktualisiertes Dokument oder None falls nicht gefunden
            
        Raises:
            RetrievalServiceError: Bei Aktualisierungsfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def get_similar_documents(
        self,
        document_id: str,
        limit: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Document]:
        """
        Findet ähnliche Dokumente zu einem gegebenen Dokument.
        
        Verwendet die semantische Ähnlichkeit zwischen Dokumenten, um
        die relevantesten verwandten Dokumente zu finden.
        
        Args:
            document_id: ID des Referenzdokuments
            limit: Maximale Anzahl zurückzugebender ähnlicher Dokumente
            score_threshold: Minimaler Ähnlichkeitsscore (0-1) für Ergebnisse
            
        Returns:
            Liste ähnlicher Dokumente, sortiert nach Ähnlichkeit
            
        Raises:
            RetrievalServiceError: Bei Fehlern in der Ähnlichkeitssuche
            
        Note:
            Der score_threshold kann verwendet werden, um nur Dokumente
            über einem bestimmten Ähnlichkeitsgrad zurückzugeben. Wenn
            nicht angegeben, werden die Top-N ähnlichsten Dokumente
            zurückgegeben.
        """
        pass