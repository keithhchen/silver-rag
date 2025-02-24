from datetime import datetime
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from app.models.document import DocumentDB, DocumentCreate, Document
from app.exceptions import DatabaseError
from loguru import logger

class DocumentService:
    def __init__(self, async_session: sessionmaker):
        self.async_session = async_session

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

                # Convert to Pydantic models
                document_list = [Document.model_validate(doc) for doc in documents]

                return {
                    "items": document_list,
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": (total_count + page_size - 1) // page_size
                }

        except Exception as e:
            raise DatabaseError(f"Failed to list documents: {str(e)}")