from fastapi import FastAPI
from loguru import logger
from app.config import Settings
from app.services.database_service import DatabaseService
from app.controllers.document_controller import router as document_router

app = FastAPI()
settings = Settings()
db_service = DatabaseService(settings)

# Register routers
app.include_router(document_router, prefix="/documents")

@app.on_event("startup")
async def startup_event():
    await db_service.init_db()
    logger.info("Application started successfully")