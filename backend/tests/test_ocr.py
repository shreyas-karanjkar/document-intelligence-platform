from pathlib import Path

from app.services.ocr_service import (
    OCRExtractionError,
    extract_text_from_uploaded_document,
)


def test_extract_text_from_pdf():
    """
    Test text extraction from a PDF.
    """

    # Create a small PDF with selectable text.
    import fitz

    document = fitz.open()

    page = document.new_page()

    page.insert_text(
        (72, 72),
        "Invoice Number: INV-1001\nTotal Amount: 1500",
    )

    pdf_bytes = document.tobytes()
    document.close()

    result = extract_text_from_uploaded_document(
        filename="test.pdf",
        file_bytes=pdf_bytes,
    )

    assert len(result) == 1
    assert result[0]["page_number"] == 1
    assert result[0]["source"] == "native_pdf"
    assert "Invoice Number" in result[0]["text"]
    assert "1500" in result[0]["text"]


def test_extract_text_from_png():
    """
    Test OCR extraction from a PNG image.
    """

    from io import BytesIO

    from PIL import Image, ImageDraw

    image = Image.new(
        "RGB",
        (800, 300),
        "white",
    )

    draw = ImageDraw.Draw(image)

    draw.text(
        (50, 50),
        "Invoice Number: INV-2001",
        fill="black",
    )

    draw.text(
        (50, 100),
        "Total Amount: 2500",
        fill="black",
    )

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    result = extract_text_from_uploaded_document(
        filename="test.png",
        file_bytes=buffer.getvalue(),
    )

    assert len(result) == 1
    assert result[0]["page_number"] == 1
    assert result[0]["source"] == "ocr"

    text = result[0]["text"]

    assert "Invoice" in text
    assert "2500" in text


def test_unsupported_file_type():

    try:
        extract_text_from_uploaded_document(
            filename="test.txt",
            file_bytes=b"some text",
        )

    except OCRExtractionError:
        return

    assert False, "Expected OCRExtractionError"