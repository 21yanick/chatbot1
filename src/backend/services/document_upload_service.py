"""
Dokument-Upload-Service-Modul.
Koordiniert den Upload-Prozess zwischen UI, Dokumentenverarbeitung und Datenbank.
"""

from typing import List, Dict, Any, Optional, BinaryIO
from datetime import datetime
import uuid
import tempfile
import os
from pathlib import Path

from src.config.settings import settings
from src.config.logging_config import (
    get_logger, 
    log_execution_time,
    log_error_with_context,
    request_context,
    log_function_call
)

from ..models.document import Document, DocumentType, DocumentStatus
from ..services.document_processor import DocumentProcessor, DocumentProcessorError
from ..utils.database import ChromaDBManager, DatabaseError
from ..services.embedding_service import EmbeddingService

# Logger für dieses Modul initialisieren
logger = get_logger(__name__)

class DocumentUploadError(Exception):
    """Spezifische Exception für Fehler beim Dokumenten-Upload."""
    pass

class DocumentUploadService:
    """
    Service für die Koordination des Dokumenten-Upload-Prozesses.
    
    Verantwortlich für:
    - Datei-Validierung und temporäre Speicherung
    - Koordination der Dokumentenverarbeitung
    - Speicherung in der Vektordatenbank
    - Status-Tracking und Fehlerbehandlung
    """
    
    def __init__(
        self,
        processor: DocumentProcessor,
        db_manager: ChromaDBManager,
        embedding_service: EmbeddingService,
        allowed_extensions: Optional[List[str]] = None,
        max_file_size: int = 10 * 1024 * 1024  # 10MB default
    ):
        """
        Initialisiert den Upload-Service.
        
        Args:
            processor: Instanz des DocumentProcessor
            db_manager: Instanz des ChromaDBManager
            embedding_service: Instanz des EmbeddingService
            allowed_extensions: Liste erlaubter Dateierweiterungen
            max_file_size: Maximale Dateigröße in Bytes
        """
        self.processor = processor
        self.db_manager = db_manager
        self.embedding_service = embedding_service
        self.allowed_extensions = allowed_extensions or ['.pdf', '.txt', '.doc', '.docx']
        self.max_file_size = max_file_size
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
    @log_function_call(logger)
    async def process_upload(
        self,
        file: BinaryIO,
        metadata: Dict[str, Any]
    ) -> Document:
        """
        Verarbeitet einen einzelnen Datei-Upload.
        
        Args:
            file: Hochgeladene Datei als BinaryIO
            metadata: Zusätzliche Metadaten für das Dokument
            
        Returns:
            Das verarbeitete Dokument
            
        Raises:
            DocumentUploadError: Bei Fehlern während der Verarbeitung
        """
        try:
            # Datei validieren
            await self._validate_file(file)
            
            # Dokument erstellen
            document = await self._create_document(file, metadata)
            
            try:
                # Inhalt direkt aus der Datei extrahieren
                file.seek(0)  # Zum Dateianfang zurückspringen
                content = await self._extract_content(file)
                document.content = content
                
                # Dokument durch Processor verarbeiten
                document.status = DocumentStatus.PROCESSING
                processed_chunks = await self.processor.process_document(document)
                
                # Embeddings erzeugen und in DB speichern
                await self._store_document_chunks(processed_chunks)
                
                # Status aktualisieren
                document.status = DocumentStatus.COMPLETED
                document.updated_at = datetime.utcnow()
                
                self.logger.info(
                    "Dokument erfolgreich verarbeitet",
                    extra={
                        "document_id": document.id,
                        "chunks_created": len(processed_chunks)
                    }
                )
                
                return document
                
            except Exception as e:
                document.status = DocumentStatus.FAILED
                document.updated_at = datetime.utcnow()
                raise e
                
        except Exception as e:
            error_context = {
                "filename": getattr(file, 'name', 'unknown'),
                "file_size": getattr(file, 'size', 0)
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Dokumenten-Upload"
            )
            raise DocumentUploadError(f"Fehler bei Dokumenten-Upload: {str(e)}")
    
    @log_function_call(logger)
    async def process_multiple_uploads(
        self,
        files: List[BinaryIO],
        shared_metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Verarbeitet mehrere Datei-Uploads parallel.
        
        Args:
            files: Liste der hochgeladenen Dateien
            shared_metadata: Gemeinsame Metadaten für alle Dokumente
            
        Returns:
            Liste der verarbeiteten Dokumente
            
        Raises:
            DocumentUploadError: Bei Fehlern während der Verarbeitung
        """
        processed_documents = []
        errors = []
        
        for file in files:
            try:
                document = await self.process_upload(file, shared_metadata)
                processed_documents.append(document)
            except Exception as e:
                errors.append(f"{getattr(file, 'name', 'unknown')}: {str(e)}")
        
        if errors:
            error_msg = "\n".join(errors)
            raise DocumentUploadError(
                f"Fehler bei {len(errors)} von {len(files)} Uploads:\n{error_msg}"
            )
        
        return processed_documents
    
    
    async def _store_document_chunks(self, chunks: List[Document]) -> None:
        """
        Speichert Dokument-Chunks in der Vektordatenbank.
        
        Args:
            chunks: Liste der zu speichernden Document-Objekte
            
        Raises:
            DocumentUploadError: Bei Fehlern während der Speicherung
                - Wenn die Embeddings nicht erstellt werden können
                - Wenn die Speicherung in der Datenbank fehlschlägt
        """
        try:
            # Listen für die Datenbank vorbereiten
            ids = []
            embeddings = []
            documents = []
            metadatas = []
            
            # Über alle Chunks iterieren und Daten sammeln
            for chunk in chunks:
                # Embedding für den Chunk erstellen
                try:
                    embedding = await self.embedding_service.get_embedding(chunk.content)
                except Exception as e:
                    raise DocumentUploadError(
                        f"Fehler bei Embedding-Erstellung für Chunk {chunk.id}: {str(e)}"
                    )
                
                # Daten für den DB-Upload sammeln
                ids.append(chunk.id)
                embeddings.append(embedding)
                documents.append(chunk.content)
                
                # Metadaten vorbereiten und Listen in Strings konvertieren
                metadata = {
                    "title": chunk.title,
                    "source_link": chunk.source_link,
                    "document_type": chunk.document_type.value,
                    "created_at": chunk.created_at.isoformat(),
                    "language": chunk.language,
                }
                
                # Zusätzliche Metadaten verarbeiten und Listen in Strings konvertieren
                for key, value in chunk.metadata.items():
                    if isinstance(value, list):
                        metadata[key] = ', '.join(map(str, value))
                    elif isinstance(value, (str, int, float, bool)):
                        metadata[key] = value
                    else:
                        metadata[key] = str(value)
                
                # Topics separat behandeln, falls vorhanden
                if hasattr(chunk, 'topics') and chunk.topics:
                    metadata['topics'] = ', '.join(map(str, chunk.topics))
                
                metadatas.append(metadata)
            
            # Chunks in der Datenbank speichern
            await self.db_manager.add_documents(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            self.logger.info(
                "Chunks erfolgreich gespeichert",
                extra={
                    "chunk_count": len(chunks),
                    "first_chunk_id": chunks[0].id if chunks else None
                }
            )
            
        except Exception as e:
            error_context = {
                "chunk_count": len(chunks),
                "first_chunk_id": chunks[0].id if chunks else None
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Chunk-Speicherung"
            )
            raise DocumentUploadError(f"Fehler bei Chunk-Speicherung: {str(e)}")
    
    async def _validate_file(self, file: BinaryIO) -> None:
        """
        Validiert eine hochgeladene Datei.
        
        Args:
            file: Zu validierende Datei
            
        Raises:
            DocumentUploadError: Bei ungültiger Datei
        """
        # Dateigröße prüfen
        if hasattr(file, 'size') and file.size > self.max_file_size:
            raise DocumentUploadError(
                f"Datei zu groß ({file.size} Bytes). "
                f"Maximum ist {self.max_file_size} Bytes"
            )
        
        # Dateierweiterung prüfen
        if hasattr(file, 'name'):
            ext = Path(file.name).suffix.lower()
            if ext not in self.allowed_extensions:
                raise DocumentUploadError(
                    f"Ungültige Dateierweiterung: {ext}. "
                    f"Erlaubt sind: {', '.join(self.allowed_extensions)}"
                )
    
    async def _create_document(
        self,
        file: BinaryIO,
        metadata: Dict[str, Any]
    ) -> Document:
        """
        Erstellt ein neues Dokument-Objekt.
        
        Args:
            file: Hochgeladene Datei
            metadata: Zusätzliche Metadaten
            
        Returns:
            Neues Dokument-Objekt
        """
        doc_id = str(uuid.uuid4())
        filename = getattr(file, 'name', 'unnamed')
        
        return Document(
            id=doc_id,
            title=metadata.get('title', filename),
            content="",  # Wird später gefüllt
            source_link=metadata['source_link'],
            document_type=metadata.get('document_type', DocumentType.SONSTIGES),
            status=DocumentStatus.PENDING,
            created_at=datetime.utcnow(),
            language=metadata.get('language', 'de'),
            category=metadata.get('category'),
            topics=metadata.get('topics', []),
            metadata={
                'original_filename': filename,
                'file_size': getattr(file, 'size', 0),
                'upload_timestamp': datetime.utcnow().isoformat(),
                **metadata.get('additional_metadata', {})
            }
        )
    
    async def _extract_content(self, file: BinaryIO) -> str:
        """
        Extrahiert den Textinhalt aus verschiedenen Dateiformaten.
        Unterstützt aktuell: PDF, TXT
        
        Args:
            file: Datei, aus der Text extrahiert werden soll
            
        Returns:
            Extrahierter Text
            
        Raises:
            DocumentUploadError: Bei Fehlern während der Extraktion
                - Wenn das Dateiformat nicht unterstützt wird
                - Wenn die Extraktion fehlschlägt
                - Wenn der extrahierte Text leer ist
        """
        try:
            # Original Dateiname für Typ-Erkennung verwenden
            original_filename = getattr(file, 'name', '').lower()
            
            # Temporäre Datei für die Verarbeitung erstellen
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                file.seek(0)  # Zum Dateianfang zurückspringen
                temp_file.write(file.read())
                temp_path = temp_file.name
            
            try:
                # Text aus TXT-Datei extrahieren
                if original_filename.endswith('.txt'):
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # Text aus PDF extrahieren
                elif original_filename.endswith('.pdf'):
                    try:
                        import PyPDF2
                    except ImportError:
                        raise DocumentUploadError(
                            "PyPDF2 ist nicht installiert. "
                            "Bitte installieren Sie es mit: pip install PyPDF2"
                        )
                    
                    content = []
                    with open(temp_path, 'rb') as pdf_file:
                        pdf_reader = PyPDF2.PdfReader(pdf_file)
                        
                        # Über alle Seiten iterieren
                        for page_num in range(len(pdf_reader.pages)):
                            page = pdf_reader.pages[page_num]
                            content.append(page.extract_text())
                    
                    content = '\n\n'.join(content)
                    
                else:
                    raise DocumentUploadError(
                        f"Dateityp nicht unterstützt: {original_filename}. "
                        "Unterstützte Formate: .txt, .pdf"
                    )
                
                # Validierung des extrahierten Inhalts
                if not content or not content.strip():
                    raise DocumentUploadError(
                        f"Kein Text aus der Datei extrahiert: {original_filename}"
                    )
                
                # Basic Text-Normalisierung
                content = content.strip()
                content = '\n'.join(line.strip() for line in content.splitlines())
                
                self.logger.info(
                    "Textextraktion erfolgreich",
                    extra={
                        "filename": original_filename,
                        "content_length": len(content),
                        "content_preview": content[:100] + "..."
                    }
                )
                
                return content
                
            finally:
                # Temporäre Datei aufräumen
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            
        except DocumentUploadError:
            raise
        except Exception as e:
            error_context = {
                "filename": original_filename,
                "error_type": type(e).__name__
            }
            log_error_with_context(
                self.logger,
                e,
                error_context,
                "Fehler bei Textextraktion"
            )
            raise DocumentUploadError(f"Fehler bei Textextraktion: {str(e)}")