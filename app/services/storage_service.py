from google.cloud import storage
from fastapi import UploadFile
from app.config import Settings
from app.exceptions import StorageError
from loguru import logger
import uuid
import datetime

class StorageService:
    def __init__(self, settings: Settings):
        self.client = storage.Client.from_service_account_json(
            settings.google_cloud_credentials
        )
        self.bucket_name = "silver-documents"
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        try:
            if not self.client.lookup_bucket(self.bucket_name):
                self.client.create_bucket(self.bucket_name)
                logger.info(f"Created new bucket: {self.bucket_name}")
        except Exception as e:
            raise StorageError(f"Failed to ensure bucket exists: {str(e)}")

    async def upload_file(self, file: UploadFile) -> str:
        try:
            bucket = self.client.bucket(self.bucket_name)
            document_id = str(uuid.uuid4())
            blob = bucket.blob(f"{document_id}/{file.filename}")

            # Read the file content
            content = await file.read()
            
            # Upload the file
            blob.upload_from_string(
                content,
                content_type=file.content_type
            )

            logger.info(f"Uploaded file {file.filename} to GCS with ID: {document_id}")
            return document_id

        except Exception as e:
            raise StorageError(f"Failed to upload file to Google Cloud Storage: {str(e)}")

        finally:
            # Reset file pointer for other services to use
            await file.seek(0)

    async def get_file(self, document_id: str):
        try:
            bucket = self.client.bucket(self.bucket_name)
            blobs = list(bucket.list_blobs(prefix=f"{document_id}/"))
            
            if not blobs:
                return None
                
            # Get the first file in the document folder
            blob = blobs[0]
            content = blob.download_as_bytes()
            
            return {
                'content': content,
                'content_type': blob.content_type,
                'filename': blob.name.split('/')[-1]
            }
            
        except Exception as e:
            raise StorageError(f"Failed to retrieve file from Google Cloud Storage: {str(e)}")

    async def get_file_url(self, document_id: str, expiration_minutes: int = 60) -> str:
        try:
            bucket = self.client.bucket(self.bucket_name)
            blobs = list(bucket.list_blobs(prefix=f"{document_id}/"))
            
            if not blobs:
                return None
                
            # Get the first file in the document folder
            blob = blobs[0]
            
            # Generate a signed URL that expires after the specified time
            url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=expiration_minutes),
                method="GET",
                response_disposition="inline",
                response_type=blob.content_type
            )
            
            logger.info(f"Generated signed URL for file with ID: {document_id}")
            return url
            
        except Exception as e:
            raise StorageError(f"Failed to generate signed URL for file: {str(e)}")

    async def delete_file(self, document_id: str) -> bool:
        try:
            bucket = self.client.bucket(self.bucket_name)
            blobs = bucket.list_blobs(prefix=f"documents/{document_id}/")
            
            deleted = False
            for blob in blobs:
                blob.delete()
                deleted = True
                logger.info(f"Deleted file from GCS with ID: {document_id}")
            
            return deleted

        except Exception as e:
            raise StorageError(f"Failed to delete file from Google Cloud Storage: {str(e)}")