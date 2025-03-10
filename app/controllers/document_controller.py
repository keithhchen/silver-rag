from fastapi import APIRouter, UploadFile, File, HTTPException, Response, Request
from loguru import logger
import traceback
from typing import Union
from app.models.document import Document
from app.exceptions import ServiceError, DatabaseError, DifyAPIError, UpstageAPIError
from app.services.database import DatabaseService
from app.config import Settings
from app.utils.pdf_splitter import PDFSplitter

router = APIRouter()
settings = Settings()
db_service = DatabaseService(settings)
document_service = db_service.document_service

@router.post("/upload", response_model=[])
async def upload_document(file: UploadFile = File(...)):
    try:
        # Split PDF if needed
        temp_files = await PDFSplitter.split_if_needed(file)

        logger.info(f"PDF split into {len(temp_files)} parts")
        results = []
        try:
            # Process each part
            for temp_file in temp_files:
                # Create a new UploadFile instance for each part
                with open(temp_file, 'rb') as f:
                    upload_file = UploadFile(filename=temp_file.name, file=f)
                    result = await document_service.process_and_store_document(upload_file)
                    results.append(result)
        except DifyAPIError as e:
            logger.error(f"Embedding service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
            raise HTTPException(status_code=500, detail=str(e))
        except DatabaseError as e:
            logger.error(f"Database service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
            raise HTTPException(status_code=400, detail=str(e))
        except UpstageAPIError as e:
            logger.error(f"OCR service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
            raise HTTPException(status_code=400, detail=str(e))
        except ServiceError as e:
            raise
        finally:
            # Clean up temporary files
            PDFSplitter.cleanup_temp_files(temp_files)
        
        return results
    except ServiceError as e:
            logger.error(f"Service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
            raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        return HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}", response_model=bool)
async def delete_document(document_id: int):
    try:
        document = await document_service.get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Document not found",
                    "message": "The requested document does not exist or has been deleted",
                    "document_id": document_id
                }
            )

        await document_service.soft_delete_document(document_id)
        return True

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"DatabaseService error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document deletion: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document deletion: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list", response_model=dict)
async def list_documents(page: int = 1, page_size: int = 10):
    try:
        return await document_service.list_documents(page=page, page_size=page_size)
    except HTTPException:
        raise
    except ServiceError as e:
        logger.error(f"Service error during document listing: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document listing: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/id/{document_id}", response_model=Document)
async def get_document(document_id: int):
    try:
        document = await document_service.get_document(document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Document not found",
                    "message": "The requested document does not exist or has been deleted",
                    "document_id": document_id
                }
            )
        return document

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"DatabaseService error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document retrieval: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document retrieval: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/single", response_model=Document)
async def lookup_single_document(
    request: Request,
    id: int = None,
    gcs_document_id: str = None,
    dify_document_id: str = None,
):

    try:
        # Validate that at least one parameter is provided
        if not any([id, gcs_document_id, dify_document_id]):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Missing identifier",
                    "message": "At least one id must be provided"
                }
            )

        # Try to find document by any of the provided identifiers
        document = None
        if id:
            document = await document_service.get_document(id)
        elif gcs_document_id:
            document = await document_service.get_document_by_gcs_id(gcs_document_id)
        elif dify_document_id:
            document = await document_service.get_document_by_dify_id(dify_document_id)

        if not document:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Document not found",
                    "message": "The requested document does not exist or has been deleted"
                }
            )

        return document

    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"DatabaseService error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}/file")
async def get_document_file(document_id: int):
    try:
        file_data = await document_service.get_document_file(document_id)
        if not file_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "File not found",
                    "message": "The document file could not be found in storage",
                    "document_id": document_id
                }
            )
            
        return { "url": file_data }
        return Response(
            content=file_data['content'],
            media_type=file_data['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{document_id}.pdf"; filename*=UTF-8''{document_id}.pdf'
            }
        )
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"DatabaseService error: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during file retrieval: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during file retrieval: {str(e)}\nTraceback: {''.join(traceback.format_tb(e.__traceback__))}")
        raise HTTPException(status_code=500, detail=str(e))