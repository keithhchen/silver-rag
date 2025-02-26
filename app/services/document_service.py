from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from fastapi import UploadFile
from typing import Optional, Dict, Any
from app.models.document import DocumentDB, DocumentCreate, Document
from app.exceptions import DatabaseError, ServiceError
from app.services.storage_service import StorageService
from app.services.upstage_service import UpstageService
from app.services.dify_service import DifyService
from loguru import logger

class DocumentService:
    def __init__(self, async_session: sessionmaker, settings):
        self.async_session = async_session
        self.storage_service = StorageService(settings)
        self.upstage_service = UpstageService(settings)
        self.dify_service = DifyService(settings)

    async def process_and_store_document(self, file: UploadFile) -> Document:
        try:
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                raise ServiceError("Invalid file type. Only PDF files are accepted")

            # Upload to Google Cloud Storage
            logger.info(f"Uploading {file.filename} to Google Cloud Storage")
            gcs_document_id = await self.storage_service.upload_file(file)

            # Process with Upstage API
            logger.info("Processing document with Upstage API")
            upstage_response = await self.upstage_service.parse_document(file)

            # Process with Dify API
            logger.info("Processing document with Dify API")
            dify_response = await self.dify_service.create_document(upstage_response.markdown, file.filename)

            # Create document record
            document_data = DocumentCreate(
                filename=file.filename,
                gcs_document_id=gcs_document_id,
                html_content=upstage_response.html,
                markdown_content=upstage_response.markdown,
                dify_document_id=dify_response.document_id,
                dify_upload_file_id=dify_response.upload_file_id
            )

            # Save to database
            return await self.create_document(document_data)

        except Exception as e:
            if isinstance(e, ServiceError):
                raise
            raise ServiceError(f"Failed to process and store document: {str(e)}")

    async def create_document(self, document_data: DocumentCreate) -> Document:
        try:
            async with self.async_session() as session:
                db_document = DocumentDB(
                    filename=document_data.filename,
                    gcs_document_id=document_data.gcs_document_id,
                    html_content=document_data.html_content,
                    markdown_content=document_data.markdown_content,
                    dify_document_id=document_data.dify_document_id,
                    dify_upload_file_id=document_data.dify_upload_file_id
                )
                session.add(db_document)
                await session.commit()
                await session.refresh(db_document)
                return Document.model_validate(db_document)

        except Exception as e:
            raise DatabaseError(f"Failed to create document record: {str(e)}")

    async def get_document(self, document_id: int) -> Document:
        try:
            async with self.async_session() as session:
                query = await session.get(DocumentDB, document_id)
                if not query or query.deleted_at:
                    return None
                return Document.model_validate(query)
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve document: {str(e)}")

    async def get_document_by_gcs_id(self, gcs_document_id: str) -> Document:
        try:
            async with self.async_session() as session:
                query = select(DocumentDB).where(
                    DocumentDB.gcs_document_id == gcs_document_id,
                    DocumentDB.deleted_at.is_(None)
                )
                result = await session.execute(query)
                document = result.scalar_one_or_none()
                if not document:
                    return None
                return Document.model_validate(document)
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve document by GCS ID: {str(e)}")

    async def get_document_by_dify_id(self, dify_document_id: str) -> Document:
        try:
            async with self.async_session() as session:
                query = select(DocumentDB).where(
                    DocumentDB.dify_document_id == dify_document_id,
                    DocumentDB.deleted_at.is_(None)
                )
                result = await session.execute(query)
                document = result.scalar_one_or_none()
                if not document:
                    return None
                return Document.model_validate(document)
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve document by Dify ID: {str(e)}")

    async def soft_delete_document(self, document_id: int) -> bool:
        try:
            async with self.async_session() as session:
                document = await session.get(DocumentDB, document_id)
                if not document or document.deleted_at:
                    return False
                document.deleted_at = datetime.utcnow()
                await session.commit()
                return True
        except Exception as e:
            raise DatabaseError(f"Failed to delete document: {str(e)}")

    async def list_documents(self, page: int = 1, page_size: int = 10):
        try:
            async with self.async_session() as session:
                # Calculate offset
                offset = (page - 1) * page_size

                # Get total count
                total_count = await session.scalar(
                    select(func.count()).select_from(DocumentDB).where(DocumentDB.deleted_at.is_(None))
                )

                # Get paginated documents
                query = select(DocumentDB)\
                    .where(DocumentDB.deleted_at.is_(None))\
                    .order_by(DocumentDB.created_at.desc())\
                    .offset(offset)\
                    .limit(page_size)

                result = await session.execute(query)
                documents = result.scalars().all()

                # Convert to Pydantic models, excluding html_content
                document_list = [{
                    "id": doc.id,
                    "filename": doc.filename,
                    "gcs_document_id": doc.gcs_document_id,
                    "markdown_content": doc.markdown_content[:300] + '...' if len(doc.markdown_content) > 300 else doc.markdown_content,
                    "dify_document_id": doc.dify_document_id,
                    "dify_upload_file_id": doc.dify_upload_file_id,
                    "created_at": doc.created_at
                } for doc in documents]

                return {
                    "items": document_list,
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }

        except Exception as e:
            raise DatabaseError(f"Failed to list documents: {str(e)}")

    async def get_document_file(self, document_id: int) -> Optional[Dict[str, Any]]:
        try:
            # Get document details to get GCS ID
            document = await self.get_document(document_id)
            if not document:
                return None
    
            # Get file from Google Cloud Storage
            content = await self.storage_service.get_file(document.gcs_document_id)
            if not content:
                return None
    
            return content
    
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve document file: {str(e)}")