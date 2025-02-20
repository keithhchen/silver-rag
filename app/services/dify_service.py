import aiohttp
from typing import NamedTuple
from app.config import Settings
from app.exceptions import DifyAPIError
from loguru import logger

class DifyResponse(NamedTuple):
    document_id: str
    upload_file_id: str

class DifyService:
    def __init__(self, settings: Settings):
        self.dataset_api_key = settings.dify_dataset_api_key
        self.dataset_id = settings.dify_dataset_id
        self.dataset_api_url = settings.dify_dataset_api_url.format(dataset_id=settings.dify_dataset_id)

    async def create_document(self, markdown_content: str, filename: str = 'document.md') -> DifyResponse:
        try:
            headers = {
                'Authorization': f"Bearer {self.dataset_api_key}"
            }

            # Create form data with the markdown content and processing rules
            form_data = aiohttp.FormData()
            form_data.add_field('file', markdown_content, filename=filename)
            form_data.add_field(
                'data',
                '{"indexing_technique": "high_quality", "doc_form": "text_model", "process_rule": {"mode": "automatic"}}'
            )
            
            api_url = f"{self.dataset_api_url}/document/create-by-file"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, data=form_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise DifyAPIError(
                            f"Dify API request failed with status {response.status}: {error_text}",
                            status_code=response.status
                        )

                    data = await response.json()
                    document = data.get('document', {})
                    data_source_info = document.get('data_source_info', {})

                    return DifyResponse(
                        document_id=document.get('id', ''),
                        upload_file_id=data_source_info.get('upload_file_id', '')
                    )

        except DifyAPIError:
            raise
        except Exception as e:
            raise DifyAPIError(f"Failed to create document in Dify: {str(e)}")

    async def delete_document(self, document_id: str) -> bool:
        try:
            headers = {
                'Authorization': f"Bearer {self.dataset_api_key}"
            }

            api_url = f"{self.dataset_api_url}/documents/{document_id}"
            async with aiohttp.ClientSession() as session:
                async with session.delete(api_url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise DifyAPIError(
                            f"Dify API delete request failed with status {response.status}: {error_text}",
                            status_code=response.status
                        )
                    
                    logger.info(f"Deleted document from Dify with ID: {document_id}")
                    return True

        except DifyAPIError:
            raise
        except Exception as e:
            raise DifyAPIError(f"Failed to delete document from Dify: {str(e)}")