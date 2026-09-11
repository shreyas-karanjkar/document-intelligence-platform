from app.schemas.extraction import (
    DocumentMetadata,
    ExtractedField,
    Evidence,
    ExtractionResult,
)

from app.services.financial_validation_service import (
    validate_financial_document,
)


def test_cash_flow_validation_passes():

    extraction = ExtractionResult(
        document_type="cash_flow",
        metadata=DocumentMetadata(
            document_title="Test Cash Flow"
        ),
        periods=["2022"],
        fields=[
            ExtractedField(
                field_name="Operating Activities",
                value="-100",
                normalized_number=-100,
                period="2022",
                evidence=Evidence(
                    source_text="Operating Activities -100",
                    page_number=1,
                ),
            ),
            ExtractedField(
                field_name="Investing Activities",
                value="-50",
                normalized_number=-50,
                period="2022",
                evidence=Evidence(
                    source_text="Investing Activities -50",
                    page_number=1,
                ),
            ),
            ExtractedField(
                field_name="Financing Activities",
                value="200",
                normalized_number=200,
                period="2022",
                evidence=Evidence(
                    source_text="Financing Activities 200",
                    page_number=1,
                ),
            ),
            ExtractedField(
                field_name="Net Increase in Cash",
                value="50",
                normalized_number=50,
                period="2022",
                evidence=Evidence(
                    source_text="Net Increase in Cash 50",
                    page_number=1,
                ),
            ),
            ExtractedField(
                field_name="Opening Cash",
                value="100",
                normalized_number=100,
                period="2022",
                evidence=Evidence(
                    source_text="Opening Cash 100",
                    page_number=1,
                ),
            ),
            ExtractedField(
                field_name="Closing Cash",
                value="150",
                normalized_number=150,
                period="2022",
                evidence=Evidence(
                    source_text="Closing Cash 150",
                    page_number=1,
                ),
            ),
        ],
    )

    result = validate_financial_document(
        extraction
    )

    assert result.overall_status == "PASS"

    assert all(
        check.status == "PASS"
        for check in result.checks
    )


def test_cash_flow_validation_fails():

    extraction = ExtractionResult(
        document_type="cash_flow",
        metadata=DocumentMetadata(
            document_title="Test Cash Flow"
        ),
        periods=["2022"],
        fields=[
            ExtractedField(
                field_name="Operating Activities",
                value="100",
                normalized_number=100,
                period="2022",
            ),
            ExtractedField(
                field_name="Investing Activities",
                value="50",
                normalized_number=50,
                period="2022",
            ),
            ExtractedField(
                field_name="Financing Activities",
                value="100",
                normalized_number=100,
                period="2022",
            ),
            ExtractedField(
                field_name="Net Increase in Cash",
                value="500",
                normalized_number=500,
                period="2022",
            ),
        ],
    )

    result = validate_financial_document(
        extraction
    )

    assert result.overall_status == "FAIL"


def test_missing_values_are_not_applicable():

    extraction = ExtractionResult(
        document_type="cash_flow",
        metadata=DocumentMetadata(
            document_title="Incomplete Cash Flow"
        ),
        periods=["2022"],
        fields=[],
    )

    result = validate_financial_document(
        extraction
    )

    assert result.overall_status == "NOT_APPLICABLE"

    assert all(
        check.status == "NOT_APPLICABLE"
        for check in result.checks
    )