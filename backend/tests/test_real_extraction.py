from pathlib import Path

from app.services.extraction_service import (
    ExtractionError,
    extract_document_data,
)
from app.services.ocr_service import (
    extract_text_from_uploaded_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

CASH_FLOW_DOCUMENT = (
    PROJECT_ROOT
    / "test_documents"
    / "cash_flow"
    / "Consolidated Cash Flow Statement 2022.pdf"
)


def test_real_cash_flow_ai_extraction():

    assert CASH_FLOW_DOCUMENT.exists(), (
        f"Test document not found: {CASH_FLOW_DOCUMENT}"
    )

    # ---------------------------------------------------------
    # STEP 1: Read the real document
    # ---------------------------------------------------------

    file_bytes = CASH_FLOW_DOCUMENT.read_bytes()

    # ---------------------------------------------------------
    # STEP 2: Extract text using our OCR/native extraction
    # service.
    # ---------------------------------------------------------

    pages = extract_text_from_uploaded_document(
        filename=CASH_FLOW_DOCUMENT.name,
        file_bytes=file_bytes,
    )

    assert pages

    # ---------------------------------------------------------
    # STEP 3: Send extracted document data to the AI
    # extraction service.
    # ---------------------------------------------------------

    try:
        result = extract_document_data(
            document_type="cash_flow",
            pages=pages,
            filename=CASH_FLOW_DOCUMENT.name,
            file_bytes=file_bytes,
        )

    except ExtractionError as exc:
        raise AssertionError(
            f"AI extraction failed: {exc}"
        ) from exc

    # ---------------------------------------------------------
    # STEP 4: Basic validation of structured result
    # ---------------------------------------------------------

    assert result is not None

    assert result.document_type == "cash_flow"

    assert result.metadata is not None

    assert len(result.periods) >= 1

    assert len(result.fields) >= 1

    # ---------------------------------------------------------
    # STEP 5: Print result for manual inspection.
    # ---------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("REAL AI EXTRACTION RESULT")
    print("=" * 70)

    print("\nDocument type:")
    print(result.document_type)

    print("\nMetadata:")
    print(result.metadata.model_dump_json(indent=2))

    print("\nPeriods:")
    for period in result.periods:
        print(f"  - {period}")

    print("\nExtracted fields:")

    for field in result.fields:

        print("\n------------------------------")

        print(f"Field: {field.field_name}")
        print(f"Original value: {field.value}")
        print(f"Normalized number: {field.normalized_number}")
        print(f"Period: {field.period}")

        if field.evidence:
            print(
                f"Page: {field.evidence.page_number}"
            )

            print(
                f"Evidence: {field.evidence.source_text}"
            )

    print("\nTables:")

    for table in result.tables:

        print("\n------------------------------")

        print(f"Table: {table.table_name}")
        print(f"Page: {table.page_number}")

        print("Columns:")

        for column in table.columns:
            print(f"  - {column}")

        print("Rows:")

        for row in table.rows:
            print(f"  {row}")

    print("\n")
    print("=" * 70)