from fastapi import APIRouter, UploadFile, File, HTTPException
from loguru import logger
from app.models.document import DocumentCreate, Document
from app.exceptions import ServiceError
from app.services.storage_service import StorageService
from app.services.upstage_service import UpstageService
from app.services.dify_service import DifyService
from app.services.database import DatabaseService
from app.config import Settings

router = APIRouter()
settings = Settings()

# Initialize services
storage_service = StorageService(settings)
upstage_service = UpstageService(settings)
dify_service = DifyService(settings)
db_service = DatabaseService(settings)

@router.post("/upload", response_model=Document)
async def upload_document(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith('.pdf'):
            logger.warning(f"Invalid file type attempted: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid file type",
                    "message": "Only PDF files are accepted",
                    "filename": file.filename
                }
            )

        # Upload to Google Cloud Storage
        logger.info(f"Uploading {file.filename} to Google Cloud Storage")
        gcs_document_id = await storage_service.upload_file(file)

        # Process with Upstage API
        logger.info("Processing document with Upstage API")
        upstage_response = await upstage_service.parse_document(file)

        # Process with Dify API
        logger.info("Processing document with Dify API")
        dify_response = await dify_service.create_document(upstage_response.markdown, file.filename)

        # Create document record
        document_data = DocumentCreate(
            filename=file.filename,
            gcs_document_id=gcs_document_id,
            html_content=upstage_response.html,
            markdown_content=upstage_response.markdown,
            dify_document_id=dify_response.document_id,
            dify_upload_file_id=dify_response.upload_file_id
        )

        # Save to database
        logger.info("Saving document information to database")
        document = await db_service.create_document(document_data)

        return document

    except ServiceError as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{document_id}", response_model=bool)
async def delete_document(document_id: int):
    try:
        # Get document details before deletion
        document = await db_service.get_document(document_id)
        logger.info(document)
        if not document:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Document not found",
                    "message": "The requested document does not exist or has been deleted",
                    "document_id": document_id
                }
            )

        # Delete from external services first
        await storage_service.delete_file(document.gcs_document_id)
        await dify_service.delete_document(document.dify_document_id)

        # Soft delete in database
        success = await db_service.soft_delete_document(document_id)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete document from database"
            )

        return True

    except ServiceError as e:
        logger.error(f"Service error during document deletion: {str(e)}")
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during document deletion: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")