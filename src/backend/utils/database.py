"""
Datenbank-Manager-Modul für ChromaDB-Integration.
Stellt die zentrale Schnittstelle für Vektordatenbank-Operationen bereit.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api import Collection
from contextlib import asynccontextmanager

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

class DatabaseError(Exception):
    """Basis-Exception für datenbankbezogene Fehler."""
    pass

class ChromaDBManager:
    """
    Manager für ChromaDB-Operationen.
    
    Verwaltet die Verbindung zu ChromaDB und stellt Methoden für
    grundlegende Datenbankoperationen bereit.
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialisiert den ChromaDB-Manager.
        
        Args:
            persist_directory: Optionaler Pfad zum Persistenz-Verzeichnis
            collection_name: Optionaler Name der Collection
        """
        self.persist_directory = persist_directory or settings.database.persist_directory
        self.collection_name = collection_name or settings.database.collection_name
        self._client = None
        self._collection = None
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    @log_function_call(logger)
    async def initialize(self) -> None:
        """
        Initialisiert ChromaDB-Client und Collection mit optimierten Einstellungen.
    
        Diese Methode:
        1. Stellt sicher, dass das Persistenz-Verzeichnis existiert
        2. Initialisiert den ChromaDB-Client mit angepassten Einstellungen
        3. Erstellt oder lädt eine Collection mit optimierten HNSW-Parametern
        4. Konfiguriert Logging und Telemetrie
    
        Raises:
            DatabaseError: Bei Fehlern während der Initialisierung, z.B.:
                - Verzeichnis nicht beschreibbar
                - Client-Initialisierung fehlgeschlagen
                - Collection-Erstellung fehlgeschlagen
        """
        try:
            with log_execution_time(self.logger, "chromadb_initialization"):
                # Verzeichnisstruktur sicherstellen
                persist_path = Path(self.persist_directory)
                persist_path.mkdir(parents=True, exist_ok=True)
            
                if not persist_path.is_dir():
                    raise DatabaseError(
                        f"Persistenz-Verzeichnis konnte nicht erstellt werden: "
                        f"{self.persist_directory}"
                    )
            
                # Client mit optimierten Einstellungen initialisieren
                self._client = chromadb.PersistentClient(
                    path=str(persist_path),
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True,
                        is_persistent=True
                    )
                )
            
                # Collection mit optimierten HNSW-Parametern erstellen/laden
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={
                        "hnsw:space": "cosine",  # Cosine-Ähnlichkeit für Embeddings
                        "hnsw:construction_ef": 100,  # Höhere Genauigkeit beim Aufbau
                        "hnsw:search_ef": 50,    # Balancierte Suche
                        "hnsw:m": 16,            # Nachbarschaftsgröße
                    }
                )
            
                self.logger.info(
                    "ChromaDB erfolgreich initialisiert",
                    extra={
                        "persist_directory": str(persist_path),
                        "collection_name": self.collection_name,
                        "collection_size": self._collection.count()
                    }
                )
            
        except Exception as e:
            error_context = {
                "persist_directory": self.persist_directory,
                "collection_name": self.collection_name
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei ChromaDB-Initialisierung"
            )
            raise DatabaseError(
                f"ChromaDB-Initialisierung fehlgeschlagen: {str(e)}"
            )
    
    @log_function_call(logger)
    async def cleanup(self) -> None:
        """Bereinigt Datenbankressourcen."""
        self.logger.info("Bereinige Datenbankressourcen")
        self._client = None
        self._collection = None
    
    @property
    def collection(self) -> Collection:
        """
        Gibt die aktuelle Collection zurück.
        
        Returns:
            Collection: Die aktuelle ChromaDB-Collection
            
        Raises:
            DatabaseError: Wenn die Datenbank nicht initialisiert ist
        """
        if self._collection is None:
            self.logger.error("Versuch auf nicht-initialisierte Datenbank zuzugreifen")
            raise DatabaseError("Datenbank nicht initialisiert")
        return self._collection
    
    @log_function_call(logger)
    async def add_documents(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Fügt Dokumente zur Collection hinzu.
        
        Args:
            ids: Liste der Dokument-IDs
            embeddings: Liste der Embedding-Vektoren
            documents: Liste der Dokument-Texte
            metadatas: Optionale Liste von Metadaten-Dictionaries
            
        Raises:
            DatabaseError: Bei Fehlern während des Hinzufügens
        """
        try:
            with log_execution_time(self.logger, "add_documents"):
                with request_context():
                    self.collection.add(
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas
                    )
                    
            self.logger.info(
                f"Erfolgreich {len(documents)} Dokumente hinzugefügt",
                extra={
                    "document_count": len(documents),
                    "first_id": ids[0] if ids else None
                }
            )
            
        except Exception as e:
            error_context = {
                "document_count": len(documents),
                "first_id": ids[0] if ids else None
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Hinzufügen von Dokumenten"
            )
            raise DatabaseError(f"Fehler beim Hinzufügen von Dokumenten: {str(e)}")
    
    @log_function_call(logger)
    async def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sucht in der Collection mittels Embeddings.
        
        Args:
            query_embeddings: Liste der Anfrage-Embedding-Vektoren
            n_results: Anzahl der gewünschten Ergebnisse
            where: Optionaler Filter für die Suche
            
        Returns:
            Dict mit Suchergebnissen
            
        Raises:
            DatabaseError: Bei Fehlern während der Suche
        """
        try:
            with log_execution_time(self.logger, "query_documents"):
                with request_context():
                    results = self.collection.query(
                        query_embeddings=query_embeddings,
                        n_results=n_results,
                        where=where
                    )
            
            self.logger.info(
                f"Suchanfrage ausgeführt",
                extra={
                    "n_results": n_results,
                    "filter_applied": bool(where),
                    "results_found": len(results.get("ids", []))
                }
            )
            
            return results
            
        except Exception as e:
            error_context = {
                "n_results": n_results,
                "where": where
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei der Dokumentensuche"
            )
            raise DatabaseError(f"Fehler bei der Dokumentensuche: {str(e)}")
    
    @log_function_call(logger)
    async def delete(self, ids: List[str]) -> None:
        """
        Löscht Dokumente anhand ihrer IDs.
        
        Args:
            ids: Liste der zu löschenden Dokument-IDs
            
        Raises:
            DatabaseError: Bei Fehlern während des Löschens
        """
        try:
            with log_execution_time(self.logger, "delete_documents"):
                with request_context():
                    self.collection.delete(ids=ids)
            
            self.logger.info(
                f"Erfolgreich {len(ids)} Dokumente gelöscht",
                extra={
                    "deleted_count": len(ids),
                    "first_deleted_id": ids[0] if ids else None
                }
            )
            
        except Exception as e:
            error_context = {
                "document_count": len(ids),
                "first_id": ids[0] if ids else None
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler beim Löschen von Dokumenten"
            )
            raise DatabaseError(f"Fehler beim Löschen von Dokumenten: {str(e)}")
    
    @log_function_call(logger)
    async def update(
        self,
        id: str,
        embedding: List[float],
        document: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Aktualisiert ein Dokument.
        
        Args:
            id: ID des zu aktualisierenden Dokuments
            embedding: Neuer Embedding-Vektor
            document: Neuer Dokumenttext
            metadata: Optionale neue Metadaten
            
        Raises:
            DatabaseError: Bei Fehlern während der Aktualisierung
        """
        try:
            with log_execution_time(self.logger, "update_document"):
                with request_context():
                    self.collection.update(
                        ids=[id],
                        embeddings=[embedding],
                        documents=[document],
                        metadatas=[metadata] if metadata else None
                    )
            
            self.logger.info(
                f"Dokument erfolgreich aktualisiert",
                extra={
                    "document_id": id,
                    "metadata_updated": bool(metadata)
                }
            )
            
        except Exception as e:
            error_context = {
                "document_id": id,
                "metadata_present": bool(metadata)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei der Dokumentaktualisierung"
            )
            raise DatabaseError(f"Fehler bei der Dokumentaktualisierung: {str(e)}")
    
    @asynccontextmanager
    async def transaction(self):
        """
        Kontext-Manager für Datenbanktransaktionen.
        
        Raises:
            DatabaseError: Bei Fehlern während der Transaktion
        """
        try:
            with request_context():
                yield self
                
        except Exception as e:
            log_error_with_context(
                self.logger,
                e,
                {},
                "Fehler während der Datenbanktransaktion"
            )
            raise DatabaseError(f"Transaktion fehlgeschlagen: {str(e)}")