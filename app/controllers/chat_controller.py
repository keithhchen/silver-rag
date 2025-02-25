from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from app.config import Settings
from app.services.chat_service import ChatService
from app.middleware.auth import JWTBearer
from pydantic import BaseModel
from loguru import logger

router = APIRouter()
settings = Settings()
chat_service = ChatService(settings)

class ChatMessageRequest(BaseModel):
    query: str
    conversation_id: str | None = None

@router.post("/messages", dependencies=[Depends(JWTBearer())])
async def send_chat_message(request: Request, chat_request: ChatMessageRequest):
    try:
        # Create async generator for streaming response
        async def generate_response():
            async for chunk in chat_service.send_chat_message(
                query=chat_request.query,
                user_id=str(request.state.user["uuid"]),
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