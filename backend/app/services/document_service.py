from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.document_repository import create_document
from app.services.document_validation_service import validate_document
from app.services.extraction_service import (
    ExtractionError,
    extract_document_data,
)
from app.services.financial_validation_service import (
    validate_financial_document,
)
from app.services.ocr_service import (
    OCRExtractionError,
    extract_text_from_uploaded_document,
)


logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Raised when the document processing pipeline fails."""


def process_document(
    db: Session,
    filename: str,
    file_bytes: bytes,
    document_type: str,
) -> dict:

    logger.info(
        "Document processing started | filename=%s | type=%s",
        filename,
        document_type,
    )

    try:

        logger.info(
            "File validation started | filename=%s",
            filename,
        )

        validate_document(
            filename=filename,
            file_bytes=file_bytes,
        )

        logger.info(
            "File validation successful | filename=%s",
            filename,
        )

    except Exception as exc:

        logger.warning(
            "File validation failed | filename=%s | error=%s",
            filename,
            str(exc),
        )

        raise DocumentProcessingError(
            f"Document validation failed: {exc}"
        ) from exc

    try:

        logger.info(
            "Text extraction/OCR started | filename=%s",
            filename,
        )

        pages = extract_text_from_uploaded_document(
            filename=filename,
            file_bytes=file_bytes,
        )

        logger.info(
            "Text extraction/OCR completed | "
            "filename=%s | pages=%d",
            filename,
            len(pages),
        )

    except OCRExtractionError as exc:

        logger.exception(
            "Text extraction/OCR failed | filename=%s",
            filename,
        )

        raise DocumentProcessingError(
            f"Text extraction/OCR failed: {exc}"
        ) from exc

    try:

        logger.info(
            "AI extraction started | filename=%s | type=%s",
            filename,
            document_type,
        )

        extraction_result = extract_document_data(
            document_type=document_type,
            pages=pages,
            filename=filename,
            file_bytes=file_bytes,
        )

        logger.info(
            "AI extraction completed | "
            "filename=%s | fields=%d | tables=%d | line_items=%d",
            filename,
            len(extraction_result.fields),
            len(extraction_result.tables),
            len(extraction_result.invoice_line_items),
        )

    except ExtractionError as exc:

        logger.exception(
            "AI extraction failed | filename=%s",
            filename,
        )

        raise DocumentProcessingError(
            f"AI extraction failed: {exc}"
        ) from exc

    try:

        logger.info(
            "Financial validation started | filename=%s",
            filename,
        )

        financial_validation = (
            validate_financial_document(
                extraction=extraction_result,
            )
        )

        logger.info(
            "Financial validation completed | "
            "filename=%s | status=%s",
            filename,
            financial_validation.overall_status,
        )

    except Exception as exc:

        logger.exception(
            "Financial validation failed | filename=%s",
            filename,
        )

        raise DocumentProcessingError(
            f"Financial validation failed: {exc}"
        ) from exc

    if (
        financial_validation.overall_status
        == "FAIL"
    ):

        processing_status = "FAILED"

    else:

        processing_status = "PASS"

    logger.info(
        "Processing status determined | "
        "filename=%s | status=%s",
        filename,
        processing_status,
    )

    extraction_dict = (
        extraction_result.model_dump(
            mode="json"
        )
    )

    validation_dict = (
        financial_validation.model_dump(
            mode="json"
        )
    )

    try:

        logger.info(
            "Saving processing result to database | "
            "filename=%s",
            filename,
        )

        document = create_document(
            db=db,
            document_name=filename,
            document_type=document_type,
            processing_status=processing_status,
            extraction_result=extraction_dict,
            financial_validation_result=validation_dict,
        )

        logger.info(
            "Processing result saved successfully | "
            "filename=%s | document_id=%s",
            filename,
            document.id,
        )

    except Exception as exc:

        logger.exception(
            "Database persistence failed | filename=%s",
            filename,
        )

        raise DocumentProcessingError(
            f"Database persistence failed: {exc}"
        ) from exc

    logger.info(
        "Document processing completed | "
        "filename=%s | document_id=%s | status=%s",
        filename,
        document.id,
        processing_status,
    )

    return {
        "id": document.id,
        "document_name": document.document_name,
        "document_type": document.document_type,
        "processing_status": (
            document.processing_status
        ),
        "extraction_result": extraction_dict,
        "financial_validation_result": (
            validation_dict
        ),
        "created_at": (
            document.created_at.isoformat()
        ),
    }