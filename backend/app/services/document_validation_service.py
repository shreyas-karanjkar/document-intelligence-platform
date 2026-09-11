from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, UnidentifiedImageError

from app.core.config import settings


ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class DocumentValidationError(Exception):
    """Raised when an uploaded document fails validation."""


def validate_file_extension(filename: str) -> None:
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            "Unsupported file type. Only PDF, JPG, JPEG, and PNG files are allowed."
        )


def validate_file_not_empty(file_bytes: bytes) -> None:
    if not file_bytes:
        raise DocumentValidationError("The uploaded file is empty.")


def validate_file_size(file_bytes: bytes) -> None:
    max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024

    if len(file_bytes) > max_file_size_bytes:
        raise DocumentValidationError(
            f"The uploaded file exceeds the maximum allowed size "
            f"of {settings.max_file_size_mb} MB."
        )


def validate_pdf(file_bytes: bytes) -> None:
    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )
    except Exception as exc:
        raise DocumentValidationError(
            "The uploaded PDF is corrupted or cannot be opened."
        ) from exc

    try:
        page_count = len(document)

        if page_count == 0:
            raise DocumentValidationError(
                "The uploaded PDF contains no pages."
            )

        if page_count > settings.max_pages:
            raise DocumentValidationError(
                f"The document contains {page_count} pages. "
                f"The maximum allowed is {settings.max_pages} pages."
            )
    finally:
        document.close()


def validate_image(file_bytes: bytes) -> None:
    try:
        image = Image.open(BytesIO(file_bytes))
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise DocumentValidationError(
            "The uploaded image is corrupted or cannot be read."
        ) from exc


def validate_document(
    filename: str,
    file_bytes: bytes,
) -> None:
    """
    Perform basic document validation before extraction.
    """

    validate_file_extension(filename)
    validate_file_not_empty(file_bytes)
    validate_file_size(file_bytes)

    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        validate_pdf(file_bytes)

    elif extension in {".jpg", ".jpeg", ".png"}:
        validate_image(file_bytes)