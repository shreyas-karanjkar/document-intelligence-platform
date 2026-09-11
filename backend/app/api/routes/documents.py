from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.repositories.document_repository import (
    document_to_dict,
    get_all_documents,
    get_latest_document_by_name,
)
from app.services.document_service import (
    DocumentProcessingError,
    process_document,
)


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


logger = get_logger(__name__)


ALLOWED_DOCUMENT_TYPES = {
    "invoice",
    "balance_sheet",
    "profit_loss",
    "cash_flow",
}


@router.post("/process")
async def process_document_endpoint(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload and process a financial document.
    """

    logger.info(
        "Document processing request received | "
        "filename=%s | document_type=%s",
        file.filename,
        document_type,
    )

    document_type = document_type.strip().lower()

    if document_type not in ALLOWED_DOCUMENT_TYPES:

        logger.warning(
            "Invalid document type | document_type=%s",
            document_type,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_DOCUMENT_TYPE",
                "message": (
                    "document_type must be one of: "
                    "invoice, balance_sheet, "
                    "profit_loss, cash_flow."
                ),
            },
        )

    filename = file.filename or ""

    if not filename.strip():

        logger.warning(
            "Upload rejected because filename is missing"
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_FILENAME",
                "message": (
                    "Uploaded file must have a filename."
                ),
            },
        )

    try:

        file_bytes = await file.read()

        logger.info(
            "File successfully read | filename=%s | size=%d bytes",
            filename,
            len(file_bytes),
        )

    except Exception as exc:

        logger.exception(
            "Failed to read uploaded file | filename=%s",
            filename,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FILE_READ_FAILED",
                "message": "Unable to read uploaded file.",
            },
        ) from exc

    try:

        result = process_document(
            db=db,
            filename=filename,
            file_bytes=file_bytes,
            document_type=document_type,
        )

        logger.info(
            "Document processing completed successfully | "
            "filename=%s | document_type=%s",
            filename,
            document_type,
        )

        return result

    except DocumentProcessingError as exc:

        logger.warning(
            "Document processing failed | "
            "filename=%s | error=%s",
            filename,
            str(exc),
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "DOCUMENT_PROCESSING_FAILED",
                "message": str(exc),
            },
        ) from exc

    except Exception as exc:

        logger.exception(
            "Unexpected error during document processing | "
            "filename=%s",
            filename,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "INTERNAL_SERVER_ERROR",
                "message": (
                    "An unexpected error occurred "
                    "while processing the document."
                ),
            },
        ) from exc


@router.get("/{document_name}")
def get_document(
    document_name: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve the latest processing result for a document.
    """

    logger.info(
        "Document retrieval requested | document_name=%s",
        document_name,
    )

    document = get_latest_document_by_name(
        db=db,
        document_name=document_name,
    )

    if document is None:

        logger.warning(
            "Document not found | document_name=%s",
            document_name,
        )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "DOCUMENT_NOT_FOUND",
                "message": (
                    f"No document found with name "
                    f"'{document_name}'."
                ),
            },
        )

    logger.info(
        "Document retrieved successfully | document_name=%s",
        document_name,
    )

    return document_to_dict(document)


@router.get("")
def list_documents(
    db: Session = Depends(get_db),
):
    """
    Retrieve all processed documents.
    """

    logger.info(
        "Processed document list requested"
    )

    documents = get_all_documents(
        db=db
    )

    logger.info(
        "Processed document list retrieved | count=%d",
        len(documents),
    )

    return {
        "count": len(documents),
        "documents": [
            document_to_dict(document)
            for document in documents
        ],
    }