from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.document import Document
from app.repositories.document_repository import (
    create_document,
    get_all_documents,
    get_latest_document_by_name,
)


def test_database_persistence():

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False
        },
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(
        bind=engine
    )

    db = TestingSessionLocal()

    try:

        created = create_document(
            db=db,
            document_name="test_cash_flow.pdf",
            document_type="cash_flow",
            processing_status="PASS",
            extraction_result={
                "document_type": "cash_flow",
                "fields": [
                    {
                        "field_name": "Net Increase in Cash",
                        "value": "100",
                    }
                ],
            },
            financial_validation_result={
                "overall_status": "PASS",
                "checks": [],
            },
        )

        assert created.id is not None

        retrieved = get_latest_document_by_name(
            db=db,
            document_name="test_cash_flow.pdf",
        )

        assert retrieved is not None

        assert (
            retrieved.document_name
            == "test_cash_flow.pdf"
        )

        assert (
            retrieved.processing_status
            == "PASS"
        )

        documents = get_all_documents(
            db=db
        )

        assert len(documents) == 1

    finally:

        db.close()
        Base.metadata.drop_all(
            bind=engine
        )
        engine.dispose()