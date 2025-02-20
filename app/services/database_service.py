from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.models.document import Base, DocumentDB, DocumentCreate, Document
from app.exceptions import DatabaseError
from loguru import logger

class DatabaseService:
    def __init__(self, settings: Settings):
        self.engine = create_async_engine(settings.database_url)
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {str(e)}")

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