# src/backend/config/__init__.py
"""Configuration module for the application."""

from .logging_config import setup_logging, get_logger
from .settings import Settings  # Import only the class

# Create settings instance here
settings = Settings()

__all__ = ['setup_logging', 'get_logger', 'settings']