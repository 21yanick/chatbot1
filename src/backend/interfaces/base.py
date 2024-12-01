"""
Basis-Modul für Service- und Repository-Interfaces.
Definiert grundlegende Abstraktion für die Service-Architektur.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Optional, List, Dict
from pydantic import BaseModel

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

# TypeVar für generische Repository-Implementierung
T = TypeVar('T', bound=BaseModel)

class ServiceError(Exception):
    """
    Basis-Exception für Service-bezogene Fehler.
    
    Attributes:
        message: Fehlermeldung
        details: Zusätzliche Fehlerdetails als Dictionary
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Initialisiert die ServiceError Exception.
        
        Args:
            message: Beschreibende Fehlermeldung
            details: Optionale zusätzliche Fehlerdetails
        """
        self.message = message
        self.details = details or {}
        super().__init__(message)
        
        # Fehler loggen
        logger.error(
            self.message,
            extra={
                "error_type": self.__class__.__name__,
                "error_details": self.details
            }
        )

class BaseService(ABC):
    """
    Basisklasse für alle Services.
    
    Definiert die grundlegende Schnittstelle für Service-Initialisierung
    und Ressourcenbereinigung.
    """
    
    def __init__(self):
        """Initialisiert den Service mit einem spezifischen Logger."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialisiert Service-Ressourcen.
        
        Diese Methode muss von allen Service-Implementierungen überschrieben werden,
        um ihre spezifische Initialisierungslogik zu implementieren.
        
        Raises:
            ServiceError: Bei Initialisierungsfehlern
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """
        Bereinigt Service-Ressourcen.
        
        Diese Methode muss von allen Service-Implementierungen überschrieben werden,
        um ihre spezifische Bereinigungslogik zu implementieren.
        
        Raises:
            ServiceError: Bei Bereinigungsfehlern
        """
        pass

class BaseRepository(Generic[T], ABC):
    """
    Basis-Repository-Interface für CRUD-Operationen.
    
    Definiert die grundlegende Schnittstelle für Datenzugriffs-Operationen.
    Generic über den Typ T, der ein Pydantic BaseModel sein muss.
    """
    
    def __init__(self):
        """Initialisiert das Repository mit einem spezifischen Logger."""
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    @abstractmethod
    async def create(self, item: T) -> T:
        """
        Erstellt einen neuen Eintrag.
        
        Args:
            item: Zu erstellendes Item
            
        Returns:
            Erstelltes Item
            
        Raises:
            ServiceError: Bei Erstellungsfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def read(self, id: str) -> Optional[T]:
        """
        Liest einen Eintrag anhand seiner ID.
        
        Args:
            id: ID des zu lesenden Items
            
        Returns:
            Gefundenes Item oder None falls nicht gefunden
            
        Raises:
            ServiceError: Bei Lesefehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def update(self, id: str, item: T) -> Optional[T]:
        """
        Aktualisiert einen bestehenden Eintrag.
        
        Args:
            id: ID des zu aktualisierenden Items
            item: Neue Itemdaten
            
        Returns:
            Aktualisiertes Item oder None falls nicht gefunden
            
        Raises:
            ServiceError: Bei Aktualisierungsfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """
        Löscht einen Eintrag anhand seiner ID.
        
        Args:
            id: ID des zu löschenden Items
            
        Returns:
            True wenn erfolgreich gelöscht, False falls nicht gefunden
            
        Raises:
            ServiceError: Bei Löschfehlern
        """
        pass
    
    @log_function_call(logger)
    @abstractmethod
    async def list(self, filter_params: Optional[Dict[str, Any]] = None) -> List[T]:
        """
        Listet Einträge mit optionaler Filterung.
        
        Args:
            filter_params: Optionale Filter-Parameter
            
        Returns:
            Liste der gefundenen Items
            
        Raises:
            ServiceError: Bei Auflistungsfehlern
        """
        pass