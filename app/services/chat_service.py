import aiohttp
import asyncio
from typing import Optional, AsyncGenerator
from app.config import Settings
from app.exceptions import DifyAPIError
from loguru import logger
from app.models.user import UserLog
from app.services.database import Session
from app.services.user_service import UserService

class ChatService:
    def __init__(self, settings: Settings):
        self.chat_api_key = settings.dify_api_key
        self.chat_api_url = settings.dify_api_url
        self.user_service = UserService(Session)

    async def send_chat_message(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        try:
            headers = {
                'Authorization': f'Bearer {self.chat_api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'inputs': {},
                'query': query,
                'response_mode': 'streaming',
                'conversation_id': conversation_id or '',
                'user': str(user_id)
            }

            # Log user chat activity asynchronously in the background
            asyncio.create_task(
                self.user_service.log_activity(
                    user_id=int(user_id),
                    action='chat_message',
                    details=query
                )
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.chat_api_url}/chat-messages',
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise DifyAPIError(
                            f'Dify Chat API request failed with status {response.status}: {error_text}',
                            status_code=response.status
                        )

                    # Handle streaming response
                    async for line in response.content:
                        if line:
                            yield line.decode('utf-8')

        except DifyAPIError:
            raise
        except Exception as e:
            raise DifyAPIError(f'Failed to send chat message to Dify: {str(e)}')