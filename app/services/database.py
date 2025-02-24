from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.exceptions import DatabaseError
from app.models.base import Base
from app.models.user import UserDB, UserLog
from app.services.document_service import DocumentService
from app.services.user_service import UserService
from loguru import logger

# Export Session for use in other services
Session = None

class DatabaseService:
    def __init__(self, settings: Settings):
        self.engine = create_async_engine(settings.database_url)
        self.async_session = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        # Set the global Session
        global Session
        Session = self.async_session
        
        self.document_service = DocumentService(self.async_session)
        self.user_service = UserService(self.async_session)

    async def init_db(self):
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {str(e)}")