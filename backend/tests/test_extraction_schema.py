from app.schemas.extraction import (
    DocumentMetadata,
    Evidence,
    ExtractedField,
    ExtractedTable,
    ExtractionResult,
)


def test_extraction_schema():

    result = ExtractionResult(
        document_type="cash_flow",
        metadata=DocumentMetadata(
            document_title="Consolidated Cash Flow Statement",
            currency="INR",
            entity_name="Example Company",
        ),
        periods=[
            "March 31, 2022",
            "March 31, 2021",
        ],
        fields=[
            ExtractedField(
                field_name="Net cash flow from operating activities",
                value="(11,959.57)",
                normalized_number=-11959.57,
                period="March 31, 2022",
                evidence=Evidence(
                    source_text=(
                        "Net cash flow (used in) / from operating activities "
                        "(11,959.57)"
                    ),
                    page_number=1,
                ),
            )
        ],
        tables=[
            ExtractedTable(
                table_name="Cash Flow Statement",
                columns=[
                    "Particulars",
                    "March 31, 2022",
                    "March 31, 2021",
                ],
                rows=[
                    [
                        "Net cash flow from operating activities",
                        "(11,959.57)",
                        "42,476.45",
                    ]
                ],
                page_number=1,
            )
        ],
    )

    assert result.document_type == "cash_flow"
    assert len(result.periods) == 2
    assert len(result.fields) == 1
    assert len(result.tables) == 1

    assert (
        result.fields[0].normalized_number
        == -11959.57
    )

    assert (
        result.fields[0].evidence.page_number
        == 1
    )