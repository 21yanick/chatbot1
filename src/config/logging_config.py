import logging
import logging.config
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from contextvars import ContextVar
from contextlib import contextmanager

# Context Variable für Request-ID Tracking
request_id_context: ContextVar[str] = ContextVar('request_id', default='')

class RequestIdFilter(logging.Filter):
    """
    Filter zur Anreicherung der Log-Nachrichten mit Request-IDs.
    Fügt jedem Log-Eintrag eine eindeutige Request-ID hinzu.
    """
    
    def filter(self, record):
        record.request_id = request_id_context.get('')
        return True

@contextmanager
def request_context():
    """
    Kontext-Manager für das Request-Tracking.
    
    Erzeugt eine neue Request-ID und stellt diese im aktuellen Kontext zur Verfügung.
    
    Beispiel:
        with request_context():
            logger.info("Verarbeite Benutzeranfrage")
    """
    token = request_id_context.set(str(uuid.uuid4()))
    try:
        yield
    finally:
        request_id_context.reset(token)

@contextmanager
def log_execution_time(logger: logging.Logger, operation_name: str):
    """
    Kontext-Manager zum Tracking der Ausführungszeit von Operationen.
    
    Args:
        logger: Der Logger für die Zeiterfassung
        operation_name: Name/Beschreibung der Operation
    
    Beispiel:
        with log_execution_time(logger, "Dokumentenverarbeitung"):
            process_documents()
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        execution_time = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"{operation_name} ausgeführt",
            extra={
                "execution_time": execution_time,
                "operation": operation_name
            }
        )

def log_error_with_context(
    logger: logging.Logger,
    error: Exception,
    context: Dict[str, Any],
    message: str = "Ein Fehler ist aufgetreten"
) -> None:
    """
    Erweiterte Fehlerprotokollierung mit zusätzlichem Kontext und Stacktrace.
    
    Diese Funktion bietet eine einheitliche Methode zur Fehlerprotokollierung mit:
    - Strukturiertem Fehlerkontext
    - Stacktrace-Informationen
    - Zusätzlichen Metadaten
    - Einheitlichem Logging-Format
    
    Args:
        logger: Logger-Instanz für die Protokollierung
        error: Die aufgetretene Exception
        context: Dictionary mit zusätzlichen Kontextinformationen
        message: Optionale Fehlermeldung (Standard: "Ein Fehler ist aufgetreten")
    
    Beispiel:
        try:
            process_document(doc)
        except Exception as e:
            log_error_with_context(
                logger,
                e,
                {'document_id': doc.id, 'operation': 'processing'}
            )
    """
    # Fehlerinformationen strukturieren
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Fehler mit ERROR-Level protokollieren
    logger.error(
        f"{message}: {error_info['error_type']} - {error_info['error_message']}",
        extra={
            'error_details': error_info,
            'stack_trace': logging.traceback.format_exc()
        }
    )

def setup_logging(
    debug: bool = False,
    log_dir: str = "logs",
    enable_performance_logging: bool = True
) -> None:
    """
    Hauptfunktion zur Konfiguration des Logging-Systems.
    
    Args:
        debug: Aktiviert detailliertere Logging-Ausgaben
        log_dir: Basisverzeichnis für Log-Dateien
        enable_performance_logging: Aktiviert separates Performance-Logging
    """
    
    # Erstelle Verzeichnisstruktur
    logs_dir = Path(log_dir)
    date_dir = logs_dir / datetime.now().strftime("%Y-%m")
    date_dir.mkdir(parents=True, exist_ok=True)
    
    # Basis-Logging-Konfiguration
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        
        "formatters": {
            "detailed": {
                "format": "%(asctime)s [%(levelname)8s] [%(request_id)s] %(name)s - %(message)s (%(filename)s:%(lineno)s)",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "simple": {
                "format": "%(levelname)s: %(message)s"
            },
            "performance": {
                "format": "%(asctime)s [PERFORMANCE] [%(request_id)s] %(message)s - Zeit: %(execution_time).2fms"
            }
        },
        
        "filters": {
            "request_id": {
                "()": RequestIdFilter
            }
        },
        
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG" if debug else "INFO",
                "formatter": "simple",
                "stream": sys.stdout,
                "filters": ["request_id"]
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": str(date_dir / "app.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8",
                "filters": ["request_id"]
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": str(date_dir / "error.log"),
                "maxBytes": 10485760,
                "backupCount": 5,
                "encoding": "utf-8",
                "filters": ["request_id"]
            },
            "debug_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "DEBUG",
                "formatter": "detailed",
                "filename": str(date_dir / "debug.log"),
                "maxBytes": 10485760,
                "backupCount": 3,
                "encoding": "utf-8",
                "filters": ["request_id"]
            }
        },
        
        "loggers": {
            "": {  # Root Logger
                "handlers": ["console", "file", "error_file"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": True
            },
            "chat_service": {
                "handlers": ["file", "error_file"],
                "level": "INFO",
                "propagate": True
            },
            "document_service": {
                "handlers": ["file", "error_file"],
                "level": "INFO",
                "propagate": True
            },
            "chromadb": {
                "handlers": ["file"],
                "level": "WARNING",
                "propagate": False
            },
            "debug": {
                "handlers": ["debug_file"],
                "level": "DEBUG",
                "propagate": False
            }
        }
    }
    
    # Performance-Logging hinzufügen wenn aktiviert
    if enable_performance_logging:
        config["handlers"]["performance_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "performance",
            "filename": str(date_dir / "performance.log"),
            "maxBytes": 10485760,
            "backupCount": 3,
            "encoding": "utf-8",
            "filters": ["request_id"]
        }
        config["loggers"]["performance"] = {
            "handlers": ["performance_file"],
            "level": "INFO",
            "propagate": False
        }
    
    # Konfiguration anwenden
    logging.config.dictConfig(config)

def get_logger(name: str) -> logging.Logger:
    """
    Erstellt oder holt einen benannten Logger.
    
    Args:
        name: Name des Loggers, üblicherweise der Modulname (__name__)
    
    Returns:
        Konfigurierter Logger für das angegebene Modul
    
    Beispiel:
        logger = get_logger(__name__)
        logger.info("Eine Info-Nachricht")
        logger.error("Ein Fehler ist aufgetreten")
    """
    return logging.getLogger(name)

def log_function_call(logger: logging.Logger):
    """
    Decorator für das Logging von Funktionsaufrufen.
    
    Protokolliert automatisch Start, Ende und eventuelle Fehler von Funktionsaufrufen.
    
    Args:
        logger: Der Logger, der verwendet werden soll
    
    Beispiel:
        @log_function_call(get_logger(__name__))
        def meine_funktion(param1, param2):
            # Funktionscode hier
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(f"Starte Funktion: {func_name}")
            try:
                with log_execution_time(logger, func_name):
                    result = func(*args, **kwargs)
                logger.debug(f"Funktion {func_name} erfolgreich beendet")
                return result
            except Exception as e:
                log_error_with_context(
                    logger,
                    e,
                    {
                        'function': func_name,
                        'args': args,
                        'kwargs': kwargs
                    }
                )
                raise
        return wrapper
    return decorator