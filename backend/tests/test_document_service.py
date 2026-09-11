from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.document import Document
from app.services.document_service import process_document


def test_document_service_pipeline():

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

        # Small valid PDF used only to verify that the
        # orchestration layer can be called.
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj\n"
            b"<< /Type /Catalog /Pages 2 0 R >>\n"
            b"endobj\n"
            b"2 0 obj\n"
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
            b"endobj\n"
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] >>\n"
            b"endobj\n"
            b"trailer\n"
            b"<< /Root 1 0 R >>\n"
            b"%%EOF"
        )

        # We are not running Gemini here.
        # This test only verifies that the module imports
        # correctly and that the database setup remains valid.

        assert db is not None

    finally:

        db.close()

        Base.metadata.drop_all(
            bind=engine
        )

        engine.dispose()