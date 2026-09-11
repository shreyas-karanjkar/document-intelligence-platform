import fitz
import pytest

from app.services.document_validation_service import (
    DocumentValidationError,
    validate_document,
)


def create_pdf(page_count: int = 1) -> bytes:
    document = fitz.open()

    for _ in range(page_count):
        document.new_page()

    pdf_bytes = document.tobytes()
    document.close()

    return pdf_bytes


def create_png() -> bytes:
    from io import BytesIO

    from PIL import Image

    image = Image.new("RGB", (100, 100), "white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")

    return buffer.getvalue()


def test_valid_pdf():
    pdf_bytes = create_pdf(1)

    validate_document(
        filename="test.pdf",
        file_bytes=pdf_bytes,
    )


def test_valid_png():
    png_bytes = create_png()

    validate_document(
        filename="test.png",
        file_bytes=png_bytes,
    )


def test_unsupported_file_type():
    with pytest.raises(DocumentValidationError):
        validate_document(
            filename="test.txt",
            file_bytes=b"some text",
        )


def test_empty_file():
    with pytest.raises(DocumentValidationError):
        validate_document(
            filename="test.pdf",
            file_bytes=b"",
        )


def test_corrupted_pdf():
    with pytest.raises(DocumentValidationError):
        validate_document(
            filename="test.pdf",
            file_bytes=b"This is not a valid PDF",
        )


def test_pdf_more_than_three_pages():
    pdf_bytes = create_pdf(4)

    with pytest.raises(DocumentValidationError):
        validate_document(
            filename="test.pdf",
            file_bytes=pdf_bytes,
        )


def test_file_size_exceeds_limit():
    file_bytes = b"0" * (11 * 1024 * 1024)

    with pytest.raises(DocumentValidationError):
        validate_document(
            filename="large.pdf",
            file_bytes=file_bytes,
        )