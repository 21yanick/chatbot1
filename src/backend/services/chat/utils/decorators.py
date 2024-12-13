"""
Logging Decorators Modul für einheitliches Logging über alle Services.
Kombiniert verschiedene Logging-Aspekte in wiederverwendbare Decorators.
"""

import asyncio
import time
import functools
from typing import Any, Callable, TypeVar, ParamSpec
from contextlib import contextmanager
from datetime import datetime

from src.config.logging_config import get_logger

# Type Vars für bessere Type Hints
P = ParamSpec("P")
T = TypeVar("T")

logger = get_logger(__name__)

def combined_logging_decorator(
    _func: Callable[P, T] = None,
    *,
    log_args: bool = True,
    log_result: bool = False,
    exclude_args: set[str] = None
):
    """
    Kombinierter Logging-Decorator für Methoden und Funktionen.
    
    Loggt:
    - Funktionsaufruf mit Argumenten (optional)
    - Ausführungszeit
    - Ergebnis (optional)
    - Fehler mit Stack Trace
    
    Args:
        _func: Die zu dekorierende Funktion
        log_args: Ob Argumente geloggt werden sollen
        log_result: Ob das Ergebnis geloggt werden soll
        exclude_args: Set von Argument-Namen die nicht geloggt werden sollen
        
    Returns:
        Dekorierte Funktion
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            func_logger = get_logger(f"{func.__module__}.{func.__name__}")
            start_time = time.time()
            
            # Argumente für Logging vorbereiten
            call_args = {}
            if log_args:
                # Args in Dict konvertieren
                call_args = {
                    **dict(zip(func.__code__.co_varnames, args)),
                    **kwargs
                }
                # Ausgeschlossene Args entfernen
                if exclude_args:
                    call_args = {
                        k: v for k, v in call_args.items()
                        if k not in exclude_args
                    }
                # self und cls aus Logging entfernen
                call_args.pop('self', None)
                call_args.pop('cls', None)
            
            try:
                # Funktionsaufruf loggen
                func_logger.debug(
                    f"Starte {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "arguments": call_args if log_args else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # Funktion ausführen
                result = await func(*args, **kwargs)
                
                # Ausführungszeit berechnen
                execution_time = time.time() - start_time
                
                # Erfolgreiche Ausführung loggen
                log_data = {
                    "function": func.__name__,
                    "execution_time": f"{execution_time:.3f}s",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                if log_result:
                    log_data["result"] = str(result)
                
                func_logger.info(
                    f"Erfolgreich ausgeführt: {func.__name__}",
                    extra=log_data
                )
                
                return result
                
            except Exception as e:
                # Ausführungszeit bei Fehler
                execution_time = time.time() - start_time
                
                # Fehler loggen
                func_logger.error(
                    f"Fehler in {func.__name__}: {str(e)}",
                    extra={
                        "function": func.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "execution_time": f"{execution_time:.3f}s",
                        "arguments": call_args if log_args else None,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    exc_info=True
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            func_logger = get_logger(f"{func.__module__}.{func.__name__}")
            start_time = time.time()
            
            # Argumente für Logging vorbereiten
            call_args = {}
            if log_args:
                # Args in Dict konvertieren
                call_args = {
                    **dict(zip(func.__code__.co_varnames, args)),
                    **kwargs
                }
                # Ausgeschlossene Args entfernen
                if exclude_args:
                    call_args = {
                        k: v for k, v in call_args.items()
                        if k not in exclude_args
                    }
                # self und cls aus Logging entfernen
                call_args.pop('self', None)
                call_args.pop('cls', None)
            
            try:
                # Funktionsaufruf loggen
                func_logger.debug(
                    f"Starte {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "arguments": call_args if log_args else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # Funktion ausführen
                result = func(*args, **kwargs)
                
                # Ausführungszeit berechnen
                execution_time = time.time() - start_time
                
                # Erfolgreiche Ausführung loggen
                log_data = {
                    "function": func.__name__,
                    "execution_time": f"{execution_time:.3f}s",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                if log_result:
                    log_data["result"] = str(result)
                
                func_logger.info(
                    f"Erfolgreich ausgeführt: {func.__name__}",
                    extra=log_data
                )
                
                return result
                
            except Exception as e:
                # Ausführungszeit bei Fehler
                execution_time = time.time() - start_time
                
                # Fehler loggen
                func_logger.error(
                    f"Fehler in {func.__name__}: {str(e)}",
                    extra={
                        "function": func.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "execution_time": f"{execution_time:.3f}s",
                        "arguments": call_args if log_args else None,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    exc_info=True
                )
                raise
        
        # Wrapper basierend auf Koroutine wählen
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    if _func is None:
        return decorator
    return decorator(_func)

@contextmanager
def log_block(
    logger,
    block_name: str,
    log_args: bool = True,
    **kwargs
):
    """
    Context Manager für Block-Logging.
    
    Args:
        logger: Logger-Instanz
        block_name: Name des Log-Blocks
        log_args: Ob zusätzliche Argumente geloggt werden sollen
        **kwargs: Zusätzliche Log-Daten
    """
    start_time = time.time()
    
    try:
        if log_args and kwargs:
            logger.debug(
                f"Starte {block_name}",
                extra={
                    "block": block_name,
                    "arguments": kwargs,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        else:
            logger.debug(
                f"Starte {block_name}",
                extra={
                    "block": block_name,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        yield
        
        execution_time = time.time() - start_time
        logger.info(
            f"Block abgeschlossen: {block_name}",
            extra={
                "block": block_name,
                "execution_time": f"{execution_time:.3f}s",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            f"Fehler in Block {block_name}: {str(e)}",
            extra={
                "block": block_name,
                "error": str(e),
                "error_type": type(e).__name__,
                "execution_time": f"{execution_time:.3f}s",
                "timestamp": datetime.utcnow().isoformat()
            },
            exc_info=True
        )
        raise