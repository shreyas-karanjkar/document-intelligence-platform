from pathlib import Path

from app.services.ocr_service import (
    OCRExtractionError,
    extract_text_from_uploaded_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CASH_FLOW_DOCUMENT = (
    PROJECT_ROOT
    / "test_documents"
    / "cash_flow"
    / "Consolidated Cash Flow Statement 2022.pdf"
)


def test_real_cash_flow_document():
    """
    Test text extraction using a real uploaded cash flow statement.
    """

    assert CASH_FLOW_DOCUMENT.exists(), (
        f"Test document not found: {CASH_FLOW_DOCUMENT}"
    )

    file_bytes = CASH_FLOW_DOCUMENT.read_bytes()

    result = extract_text_from_uploaded_document(
        filename=CASH_FLOW_DOCUMENT.name,
        file_bytes=file_bytes,
    )

    assert result
    assert len(result) <= 3

    # Check that page-level information is present.
    assert result[0]["page_number"] == 1

    # The document should be processed either through
    # native PDF extraction or OCR.
    assert result[0]["source"] in {
        "native_pdf",
        "ocr",
    }

    text = result[0]["text"]

    # Check for important text that is visibly present
    # in this real document.
    assert "Consolidated Cash Flow Statement" in text
    assert "March 31, 2022" in text
    assert "March 31, 2021" in text
    assert "Cash flows from operating activities" in text

    print("\n========== REAL DOCUMENT EXTRACTION ==========")
    print(f"Document: {CASH_FLOW_DOCUMENT.name}")
    print(f"Pages processed: {len(result)}")
    print(f"Extraction source: {result[0]['source']}")
    print("\n---------- EXTRACTED TEXT ----------")
    print(text)
    print("=============================================\n")