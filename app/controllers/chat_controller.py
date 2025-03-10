from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from app.config import Settings
from app.services.chat_service import ChatService
from app.middleware.auth import JWTBearer
from pydantic import BaseModel
from loguru import logger
from app.exceptions import ServiceError, DifyAPIError
import traceback
from typing import Optional
import aiohttp

router = APIRouter()
settings = Settings()
chat_service = ChatService(settings)

class ChatMessageRequest(BaseModel):
    query: str
    conversation_id: str | None = None

@router.get("/conversations", dependencies=[Depends(JWTBearer())])
async def list_conversations(
    request: Request,
    last_id: Optional[str] = None,
    limit: Optional[int] = 20
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{settings.dify_api_url}/conversations',
                headers={'Authorization': f'Bearer {settings.dify_api_key}'},
                params={'user': str(request.state.user["uuid"]), 'last_id': last_id or '', 'limit': limit}
            ) as response:
                if response.status != 200:
                    raise DifyAPIError(
                        f'Conversation list request failed with status {response.status}: {await response.text()}',
                        status_code=response.status
                    )
                return JSONResponse(content=await response.json())
    except DifyAPIError as e:
        logger.error(f"Dify API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

@router.get("/conversations/messages", dependencies=[Depends(JWTBearer())])
async def get_conversation_messages(
    request: Request,
    conversation_id: str,
    first_id: Optional[str] = None,
    limit: Optional[int] = 20
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{settings.dify_api_url}/messages',
                headers={'Authorization': f'Bearer {settings.dify_api_key}'},
                params={
                    'user': str(request.state.user["uuid"]),
                    'conversation_id': conversation_id,
                    'first_id': first_id or '',
                    'limit': limit
                }
            ) as response:
                if response.status != 200:
                    raise DifyAPIError(
                        f'Message history request failed with status {response.status}: {await response.text()}',
                        status_code=response.status
                    )
                return JSONResponse(content=await response.json())
    except DifyAPIError as e:
        logger.error(f"Dify API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/messages/{message_id}/suggested", dependencies=[Depends(JWTBearer())])
async def get_suggested_messages(
    request: Request,
    message_id: str
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'{settings.dify_api_url}/messages/{message_id}/suggested',
                headers={'Authorization': f'Bearer {settings.dify_api_key}'},
                params={'user': str(request.state.user["uuid"])}
            ) as response:
                if response.status != 200:
                    raise DifyAPIError(
                        f'Suggested messages request failed with status {response.status}: {await response.text()}',
                        status_code=response.status
                    )
                return JSONResponse(content=await response.json())
    except DifyAPIError as e:
        logger.error(f"Dify API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))