import aiohttp
from fastapi import UploadFile
from app.config import Settings
from app.exceptions import UpstageAPIError
from loguru import logger
from typing import NamedTuple

class UpstageResponse(NamedTuple):
    html: str
    markdown: str

class UpstageService:
    def __init__(self, settings: Settings):
        self.api_key = settings.upstage_api_key
        self.api_url = settings.upstage_api_url

    async def parse_document(self, file: UploadFile) -> UpstageResponse:
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}'
            }

            form_data = aiohttp.FormData()
            content = await file.read()
            form_data.add_field('document', content, filename=file.filename)
            form_data.add_field('output_formats', '["html", "markdown"]')
            form_data.add_field('base64_encoding', '["table"]')
            form_data.add_field('chart_recognition', 'true')
            form_data.add_field('model', 'document-parse')
            form_data.add_field('ocr', 'force')

            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, data=form_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise UpstageAPIError(
                            f"OCR API request failed with status {response.status}: {error_text}",
                            status_code=response.status
                        )

                    data = await response.json()
                    content = data.get('content', {})
                    
                    return UpstageResponse(
                        html=content.get('html', ''),
                        markdown=content.get('markdown', '')
                    )

        except UpstageAPIError:
            raise
        except Exception as e:
            raise UpstageAPIError(f"Failed to parse document with OCR API: {str(e)}")

        finally:
            # Reset file pointer for other services to use
            await file.seek(0)