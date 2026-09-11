import json

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.document import Document


# ============================================================
# Create document
# ============================================================

def create_document(
    db: Session,
    document_name: str,
    document_type: str,
    processing_status: str,
    extraction_result: dict | None = None,
    financial_validation_result: dict | None = None,
    error_message: str | None = None,
) -> Document:

    document = Document(
        document_name=document_name,
        document_type=document_type,
        processing_status=processing_status,
        extraction_result=(
            json.dumps(extraction_result)
            if extraction_result is not None
            else None
        ),
        financial_validation_result=(
            json.dumps(financial_validation_result)
            if financial_validation_result is not None
            else None
        ),
        error_message=error_message,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


# ============================================================
# Get latest document by name
# ============================================================

def get_latest_document_by_name(
    db: Session,
    document_name: str,
) -> Document | None:

    return (
        db.query(Document)
        .filter(
            Document.document_name == document_name
        )
        .order_by(
            desc(Document.created_at)
        )
        .first()
    )


# ============================================================
# Get all documents
# ============================================================

def get_all_documents(
    db: Session,
) -> list[Document]:

    return (
        db.query(Document)
        .order_by(
            desc(Document.created_at)
        )
        .all()
    )


# ============================================================
# Convert database document into API-friendly dictionary
# ============================================================

def document_to_dict(
    document: Document,
) -> dict:

    extraction_result = None

    if document.extraction_result:

        extraction_result = json.loads(
            document.extraction_result
        )

    financial_validation_result = None

    if document.financial_validation_result:

        financial_validation_result = json.loads(
            document.financial_validation_result
        )

    return {
        "id": document.id,
        "document_name": document.document_name,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "extraction_result": extraction_result,
        "financial_validation_result": financial_validation_result,
        "error_message": document.error_message,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }