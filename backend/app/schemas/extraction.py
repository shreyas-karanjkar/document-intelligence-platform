from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source_text: str | None = None
    page_number: int | None = None


class ExtractedField(BaseModel):
    field_name: str
    value: str | None = None
    normalized_number: float | None = None
    period: str | None = None
    evidence: Evidence | None = None


class InvoiceLineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None
    evidence: Evidence | None = None


class ExtractedTable(BaseModel):
    table_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str | None]] = Field(default_factory=list)
    page_number: int | None = None


class DocumentMetadata(BaseModel):
    document_title: str | None = None
    document_date: str | None = None
    vendor_name: str | None = None
    customer_name: str | None = None
    entity_name: str | None = None
    currency: str | None = None


class ExtractionResult(BaseModel):
    document_type: str

    metadata: DocumentMetadata

    periods: list[str] = Field(
        default_factory=list
    )

    fields: list[ExtractedField] = Field(
        default_factory=list
    )

    tables: list[ExtractedTable] = Field(
        default_factory=list
    )

    invoice_line_items: list[InvoiceLineItem] = Field(
        default_factory=list
    )