from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from app.config import Settings
from app.services.database import DatabaseService
from app.controllers.document_controller import router as document_router
from app.controllers.user_controller import router as user_router
from app.controllers.chat_controller import router as chat_router
from app.middleware.auth_middleware import AuthMiddleware

app = FastAPI()
settings = Settings()
db_service = DatabaseService(settings)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://silver-rag-fe.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    expose_headers=["Content-Type", "Authorization"],
    max_age=600
)

# Add authentication middleware
app.middleware("http")(AuthMiddleware())

# Register routers
app.include_router(document_router, prefix="/documents")
app.include_router(user_router, prefix="/users")
app.include_router(chat_router, prefix="/chat")

@app.on_event("startup")
async def startup_event():
    await db_service.init_db()
    logger.info("Application started successfully")