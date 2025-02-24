from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.config import Settings
from app.services.chat_service import ChatService
from app.middleware.auth_middleware import get_authenticated_user
from app.models.user import User
from pydantic import BaseModel
from loguru import logger

router = APIRouter()
settings = Settings()
chat_service = ChatService(settings)

class ChatMessageRequest(BaseModel):
    query: str
    conversation_id: str | None = None

@router.post("/messages")
async def send_chat_message(
    request: Request,
    chat_request: ChatMessageRequest,
    current_user: User = Depends(get_authenticated_user)
):
    if not current_user:
        return {"detail": "Authentication required"}, 401

    try:
        # Create async generator for streaming response
        async def generate_response():
            async for chunk in chat_service.send_chat_message(
                query=chat_request.query,
                user_id=str(current_user.id),
                conversation_id=chat_request.conversation_id
            ):
                yield chunk

        return StreamingResponse(
            generate_response(),
            media_type="text/event-stream"
        )

    except Exception as e:
        logger.error(f"Error in chat message endpoint: {str(e)}")
        return {"detail": "Internal server error"}, 500