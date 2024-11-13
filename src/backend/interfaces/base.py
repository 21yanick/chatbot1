from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Optional, List, Dict
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class ServiceError(Exception):
    """Base exception for service-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

class BaseService(ABC):
    """Base class for all services."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize service resources."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        pass

class BaseRepository(Generic[T], ABC):
    """Base repository interface for CRUD operations."""
    
    @abstractmethod
    async def create(self, item: T) -> T:
        """Create a new item."""
        pass
    
    @abstractmethod
    async def read(self, id: str) -> Optional[T]:
        """Read an item by ID."""
        pass
    
    @abstractmethod
    async def update(self, id: str, item: T) -> Optional[T]:
        """Update an existing item."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete an item by ID."""
        pass
    
    @abstractmethod
    async def list(self, filter_params: Optional[Dict[str, Any]] = None) -> List[T]:
        """List items with optional filtering."""
        pass