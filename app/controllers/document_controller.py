from fastapi import APIRouter, UploadFile, File, HTTPException, Response, Request
from loguru import logger
from app.models.document import Document
from app.exceptions import ServiceError, DatabaseError, DifyAPIError
from app.services.database import DatabaseService
from app.config import Settings

router = APIRouter()
settings = Settings()
db_service = DatabaseService(settings)
document_service = db_service.document_service

@router.post("/upload", response_model=Document)
async def upload_document(file: UploadFile = File(...)):
    try:
        return await document_service.process_and_store_document(file)
    except DifyAPIError as e:
        logger.error(f"Embedding service error during document lookup: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Database service error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{document_id}", response_model=bool)
async def delete_document(document_id: int):
    try:
        # Get document details before deletion
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

        # Delete from external services first
        await document_service.soft_delete_document(document_id)
        return True

    except DatabaseError as e:
        logger.error(f"DatabaseService error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document deletion: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document deletion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=dict)
async def list_documents(page: int = 1, page_size: int = 10):
    try:
        return await document_service.list_documents(page=page, page_size=page_size)
    except ServiceError as e:
        logger.error(f"Service error during document listing: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document listing: {str(e)}")
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

    except DatabaseError as e:
        logger.error(f"DatabaseService error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document retrieval: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document retrieval: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/embedding/{dify_document_id}", response_model=Document)
async def get_document_by_dify_id(dify_document_id: str):
    try:
        document = await document_service.get_document_by_dify_id(dify_document_id)
        if not document:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Document not found",
                    "message": "The requested document does not exist or has been deleted",
                    "dify_document_id": dify_document_id
                }
            )
        return document

    except DatabaseError as e:
        logger.error(f"DatabaseService error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document retrieval: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document retrieval: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/single", response_model=Document)
async def lookup_single_document(
    request: Request,
    id: int = None,
    gcs_document_id: str = None,
    dify_document_id: str = None,
):
    # Log request information
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Query parameters: {request.query_params}")
    logger.info(f"Path parameters: {request.path_params}")

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

    except DatabaseError as e:
        logger.error(f"DatabaseService error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during document lookup: {str(e)}")
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

        return Response(
            content=file_data['content'],
            media_type=file_data['content_type'],
            headers={
                'Content-Disposition': f'inline; filename="{file_data["filename"]}"'
            }
        )
    except DatabaseError as e:
        logger.error(f"DatabaseService error during document lookup: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error during file retrieval: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during file retrieval: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))