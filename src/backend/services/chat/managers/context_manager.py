"""
Context Manager Modul für die Verarbeitung und Verwaltung von Chat-Kontexten.
Behandelt die Aufbereitung von Dokumenten und Chat-Verläufen für den LLM-Input.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from src.backend.models.chat import Message
from src.backend.models.document import Document
from src.config.settings import settings
from src.config.logging_config import get_logger, log_execution_time

class ContextManagerError(Exception):
    """Basisklasse für ContextManager-spezifische Fehler."""
    pass

class ContextManager:
    """
    Verwaltet und verarbeitet Kontext-Informationen für Chat-Interaktionen.
    
    Verantwortlich für:
    - Aufbereitung von Dokumenten-Kontext
    - Formatierung von Chat-Verläufen
    - Verwaltung von Kontext-Limits
    - Priorisierung von Kontext-Informationen
    """
    
    def __init__(
        self,
        max_context_length: Optional[int] = None,
        max_history_messages: Optional[int] = None
    ):
        """
        Initialisiert den ContextManager.
        
        Args:
            max_context_length: Maximale Länge des Dokumenten-Kontexts
            max_history_messages: Maximale Anzahl der Chat-Verlauf-Nachrichten
        """
        self.max_context_length = max_context_length or settings.chat.max_context_length
        self.max_history_messages = max_history_messages or settings.chat.max_context_messages
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def prepare_document_context(
        self,
        documents: List[Document],
        query: Optional[str] = None
    ) -> str:
        """
        Bereitet den Kontext-String aus Dokumenten vor.
        
        Args:
            documents: Liste der Kontext-Dokumente
            query: Optionale Anfrage für Kontext-Priorisierung
            
        Returns:
            Formatierter Kontext-String
            
        Raises:
            ContextManagerError: Bei Verarbeitungsfehlern
        """
        try:
            with log_execution_time(self.logger, "prepare_document_context"):
                if not documents:
                    return ""
                
                # Dokumente nach Relevanz sortieren wenn Query vorhanden
                if query:
                    documents = self._sort_documents_by_relevance(documents, query)
                
                context_parts = []
                total_length = 0
                
                for i, doc in enumerate(documents, 1):
                    # Dokumenteninhalt formatieren
                    doc_text = f"Dokument {i} ({doc.metadata.get('type', 'unbekannt')}):\n{doc.content}\n"
                    
                    # Prüfen ob Längengrenze erreicht
                    if total_length + len(doc_text) > self.max_context_length:
                        self.logger.debug(
                            "Maximale Kontextlänge erreicht",
                            extra={
                                "used_documents": i-1,
                                "total_documents": len(documents)
                            }
                        )
                        break
                    
                    context_parts.append(doc_text)
                    total_length += len(doc_text)
                
                context = "\n".join(context_parts)
                
                self.logger.info(
                    "Dokument-Kontext vorbereitet",
                    extra={
                        "document_count": len(context_parts),
                        "context_length": len(context)
                    }
                )
                
                return context
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei der Dokumenten-Kontext-Vorbereitung: {str(e)}",
                extra={"document_count": len(documents)}
            )
            raise ContextManagerError(f"Dokumenten-Kontext-Vorbereitung fehlgeschlagen: {str(e)}")

    def format_chat_history(
        self,
        messages: List[Message],
        include_metadata: bool = False
    ) -> str:
        """
        Formatiert den Chat-Verlauf für den Prompt.
        
        Args:
            messages: Liste der Chat-Nachrichten
            include_metadata: Ob Metadaten einbezogen werden sollen
            
        Returns:
            Formatierter Chat-Verlauf als String
            
        Raises:
            ContextManagerError: Bei Formatierungsfehlern
        """
        try:
            with log_execution_time(self.logger, "format_chat_history"):
                # System-Nachrichten filtern und auf maximale Anzahl begrenzen
                filtered_messages = [
                    msg for msg in messages
                    if msg.role != "system"
                ][-self.max_history_messages:]
                
                if not filtered_messages:
                    return "Keine vorherigen Nachrichten."
                
                history_parts = []
                for msg in filtered_messages:
                    # Basis-Nachrichtenformat
                    formatted_msg = f"{msg.role.capitalize()}: {msg.content}"
                    
                    # Metadaten hinzufügen wenn gewünscht
                    if include_metadata and msg.metadata:
                        meta_str = ", ".join(
                            f"{k}: {v}"
                            for k, v in msg.metadata.items()
                            if k != "type"  # System-Metadaten ausschließen
                        )
                        if meta_str:
                            formatted_msg += f" [{meta_str}]"
                    
                    history_parts.append(formatted_msg)
                
                history = "\n".join(history_parts)
                
                self.logger.debug(
                    "Chat-Verlauf formatiert",
                    extra={
                        "message_count": len(history_parts),
                        "history_length": len(history)
                    }
                )
                
                return history
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei der Chat-Verlauf-Formatierung: {str(e)}",
                extra={"message_count": len(messages)}
            )
            raise ContextManagerError(f"Chat-Verlauf-Formatierung fehlgeschlagen: {str(e)}")

    def _sort_documents_by_relevance(
        self,
        documents: List[Document],
        query: str
    ) -> List[Document]:
        """
        Sortiert Dokumente nach Relevanz zur Anfrage.
        
        Args:
            documents: Liste der zu sortierenden Dokumente
            query: Anfrage für Relevanzbestimmung
            
        Returns:
            Nach Relevanz sortierte Dokumentenliste
        """
        # TODO: Implementiere bessere Relevanz-Berechnung
        # Aktuell nur nach Datum sortiert als Platzhalter
        return sorted(
            documents,
            key=lambda x: x.metadata.get('timestamp', datetime.min),
            reverse=True
        )

    def prepare_combined_context(
        self,
        query: str,
        documents: List[Document],
        messages: List[Message],
        include_metadata: bool = False
    ) -> Dict[str, str]:
        """
        Bereitet kombinierten Kontext aus Dokumenten und Chat-Verlauf vor.
        
        Args:
            query: Benutzeranfrage
            documents: Liste der Kontext-Dokumente
            messages: Liste der Chat-Nachrichten
            include_metadata: Ob Metadaten einbezogen werden sollen
            
        Returns:
            Dict mit aufbereitetem Kontext
            
        Raises:
            ContextManagerError: Bei Verarbeitungsfehlern
        """
        try:
            with log_execution_time(self.logger, "prepare_combined_context"):
                # Dokumente und Chat-Verlauf aufbereiten
                doc_context = self.prepare_document_context(documents, query)
                chat_history = self.format_chat_history(messages, include_metadata)
                
                context = {
                    "documents": doc_context,
                    "chat_history": chat_history,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self.logger.info(
                    "Kombinierter Kontext vorbereitet",
                    extra={
                        "doc_context_length": len(doc_context),
                        "history_length": len(chat_history)
                    }
                )
                
                return context
            
        except Exception as e:
            self.logger.error(
                f"Fehler bei der Kontext-Vorbereitung: {str(e)}",
                extra={
                    "document_count": len(documents),
                    "message_count": len(messages)
                }
            )
            raise ContextManagerError(f"Kontext-Vorbereitung fehlgeschlagen: {str(e)}")