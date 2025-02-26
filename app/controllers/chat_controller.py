from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.config import Settings
from app.services.chat_service import ChatService
from app.middleware.auth import JWTBearer
from pydantic import BaseModel
from loguru import logger
from exceptions import ServiceError, DifyAPIError
import traceback

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
    
    except DifyAPIError as e:
        logger.error(f"Chat service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document lookup: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))