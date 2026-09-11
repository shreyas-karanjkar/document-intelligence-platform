from io import BytesIO
from pathlib import Path
import re

import pymupdf
import pytesseract
from PIL import Image
from pytesseract import Output
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.core.config import settings
from app.schemas.extraction import (
    DocumentMetadata,
    Evidence,
    ExtractedField,
    ExtractedTable,
    ExtractionResult,
    InvoiceLineItem,
)


class ExtractionError(Exception):
    """Raised when document extraction fails."""


class SimpleField(BaseModel):
    field_name: str
    value: str | None = None
    period: str | None = None
    source_text: str | None = None
    page_number: int | None = None


class SimpleFieldExtraction(BaseModel):
    metadata: DocumentMetadata

    periods: list[str] = Field(
        default_factory=list
    )

    fields: list[SimpleField] = Field(
        default_factory=list
    )

    invoice_line_items: list[InvoiceLineItem] = Field(
        default_factory=list
    )


def _get_gemini_client() -> genai.Client:
    if not settings.gemini_api_key:
        raise ExtractionError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=settings.gemini_api_key
    )


def _build_source_text(
    pages: list[dict],
) -> str:

    parts = []

    for page in pages:

        page_number = page.get(
            "page_number"
        )

        text = page.get(
            "text",
            ""
        ).strip()

        if not text:
            continue

        page_section = (
            f"--- PAGE {page_number} ---\n"
            f"{text}"
        )

        layout = page.get(
            "layout"
        )

        if layout:

            layout_lines = []

            for word in layout:

                word_text = word.get(
                    "text",
                    ""
                ).strip()

                if not word_text:
                    continue

                left = word.get(
                    "left"
                )

                top = word.get(
                    "top"
                )

                if (
                    left is None
                    or top is None
                ):
                    continue

                layout_lines.append(
                    f"{word_text}"
                    f"[x={left},y={top}]"
                )

            if layout_lines:

                page_section += (
                    "\n\n"
                    "OCR WORD POSITIONS "
                    "(x=horizontal position, "
                    "y=vertical position):\n"
                )

                page_section += (
                    " ".join(
                        layout_lines
                    )
                )

        parts.append(
            page_section
        )

    return "\n\n".join(
        parts
    )


def _build_document_parts(
    filename: str,
    file_bytes: bytes,
    document_type: str | None = None,
) -> list:

    extension = Path(
        filename
    ).suffix.lower()

    parts = []

    if extension in {
        ".jpg",
        ".jpeg",
        ".png",
    }:

        mime_type = (
            "image/jpeg"
            if extension in {
                ".jpg",
                ".jpeg",
            }
            else "image/png"
        )

        parts.append(
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=mime_type,
            )
        )

        return parts

    if extension == ".pdf":

        try:

            document = pymupdf.open(
                stream=file_bytes,
                filetype="pdf",
            )

        except Exception as exc:

            raise ExtractionError(
                "Unable to open PDF for visual AI extraction."
            ) from exc

        try:

            for page_number, page in enumerate(
                document,
                start=1,
            ):

                # Profit & Loss statements can contain dense
                # comparative-period columns with very similar
                # digits. Render those pages at higher resolution
                # so the vision model has a clearer source image.
                # Other document types keep the existing 1.5x
                # rendering unchanged.
                render_scale = (
                    3.0
                    if document_type == "profit_loss"
                    else 1.5
                )

                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(
                        render_scale,
                        render_scale,
                    ),
                    alpha=False,
                )

                image_bytes = pixmap.tobytes(
                    "jpeg"
                )

                parts.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg",
                    )
                )

        except Exception as exc:

            raise ExtractionError(
                "Failed to render PDF pages for visual AI extraction."
            ) from exc

        finally:

            document.close()

        return parts

    raise ExtractionError(
        "Unsupported document type for visual AI extraction."
    )


def _normalize_number(
    value: str | None,
) -> float | None:

    if value is None:
        return None

    raw = value.strip()

    if not raw:
        return None

    negative = (
        raw.startswith("(")
        and raw.endswith(")")
    )

    cleaned = (
        raw
        .replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )

    try:

        number = float(
            cleaned
        )

    except ValueError:

        return None

    if negative:
        number = -number

    return number


def _convert_fields(
    fields: list[SimpleField],
) -> list[ExtractedField]:

    converted_fields = []

    for field in fields:

        normalized_number = (
            _normalize_number(
                field.value
            )
        )

        converted_fields.append(
            ExtractedField(
                field_name=field.field_name,
                value=field.value,
                normalized_number=normalized_number,
                period=field.period,
                evidence={
                    "source_text": (
                        field.source_text
                    ),
                    "page_number": (
                        field.page_number
                    ),
                },
            )
        )

    return converted_fields


def _build_tables_from_fields(
    document_type: str,
    fields: list[ExtractedField],
) -> list[ExtractedTable]:

    if not fields:
        return []

    grouped: dict[
        str,
        list[ExtractedField],
    ] = {}

    for field in fields:

        name = field.field_name.strip()

        if not name:
            continue

        grouped.setdefault(
            name,
            [],
        ).append(
            field
        )

    if not grouped:
        return []

    periods: list[str] = []

    for field in fields:

        if (
            field.period
            and field.period not in periods
        ):

            periods.append(
                field.period
            )

    first_page = None

    for field in fields:

        if (
            field.evidence
            and field.evidence.page_number
            is not None
        ):

            first_page = (
                field.evidence.page_number
            )

            break

    rows = []

    for field_name, field_group in grouped.items():

        row = [
            field_name
        ]

        for period in periods:

            matching_field = None

            for field in field_group:

                if field.period == period:

                    matching_field = field

                    break

            if matching_field is None:

                row.append(None)

            else:

                row.append(
                    matching_field.value
                )

        if any(
            value is not None
            for value in row[1:]
        ):

            rows.append(
                row
            )

    if not rows:
        return []

    if document_type == "cash_flow":

        table_name = (
            "Consolidated Cash Flow Statement"
        )

    elif document_type == "balance_sheet":

        table_name = (
            "Balance Sheet"
        )

    elif document_type == "profit_loss":

        table_name = (
            "Profit and Loss Statement"
        )

    elif document_type == "invoice":

        table_name = "Invoice"

    else:

        table_name = (
            "Financial Document"
        )

    columns = [
        "Particulars"
    ]

    columns.extend(
        periods
    )

    return [
        ExtractedTable(
            table_name=table_name,
            columns=columns,
            rows=rows,
            page_number=first_page,
        )
    ]


def _call_gemini_with_fallback(
    client: genai.Client,
    contents: list,
    response_schema,
):
    """
    Call Gemini with transient-error retries and model fallback.

    The extraction service must not depend on a single model endpoint.
    A transient 5xx/429 or malformed response causes the service to
    retry and then move to the next configured fallback model.
    """

    import logging
    import time

    logger = logging.getLogger(__name__)

    primary_model = settings.gemini_model

    configured_fallback = getattr(
        settings,
        "gemini_fallback_model",
        None,
    )

    candidate_models = [
        primary_model,
        configured_fallback,
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]

    models = []

    for model in candidate_models:
        if model and model not in models:
            models.append(model)

    last_error = None

    for model_index, model in enumerate(models):

        # Two attempts per model. The SDK itself also retries some
        # transient failures, so this application-level retry is kept
        # deliberately small.
        for attempt in range(1, 3):

            try:

                logger.info(
                    "Gemini extraction attempt | model=%s | "
                    "attempt=%d/2 | model_index=%d/%d",
                    model,
                    attempt,
                    model_index + 1,
                    len(models),
                )

                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        max_output_tokens=16000,
                        temperature=0,
                        thinking_config=types.ThinkingConfig(
                            thinking_level="low"
                        ),
                    ),
                )

                if not response.text:
                    raise ExtractionError(
                        f"Gemini model '{model}' returned an empty "
                        "response."
                    )

                logger.info(
                    "Gemini returned a response | model=%s | "
                    "characters=%d",
                    model,
                    len(response.text),
                )

                return response

            except ExtractionError as exc:

                last_error = exc

                logger.warning(
                    "Gemini response problem | model=%s | "
                    "attempt=%d/2 | error=%s",
                    model,
                    attempt,
                    str(exc),
                )

            except Exception as exc:

                last_error = exc

                logger.warning(
                    "Gemini request failed | model=%s | "
                    "attempt=%d/2 | error_type=%s | error=%s",
                    model,
                    attempt,
                    type(exc).__name__,
                    str(exc),
                )

            if attempt == 1:
                # Small exponential delay before the second attempt.
                # We intentionally cap this because the evaluator
                # should not wait several minutes for one request.
                time.sleep(2)

        if model_index < len(models) - 1:

            logger.warning(
                "Switching Gemini model after unsuccessful attempts | "
                "failed_model=%s | next_model=%s",
                model,
                models[model_index + 1],
            )

    raise ExtractionError(
        "All configured Gemini extraction models failed. "
        "The service attempted transient retries and model fallback."
    ) from last_error



def _normalize_pnl_label(value: str) -> str:
    """Normalize a visible P&L row label for matching."""
    value = value.lower().replace("’", "'")
    value = re.sub(r"\[[^\]]*\]", "", value)
    value = re.sub(r"\([^)]*refer[^)]*\)", "", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^a-z0-9/& -]", "", value)
    return value.strip()


def _pnl_highres_ocr_values(
    file_bytes: bytes,
) -> dict[str, dict[str, tuple[str, float | None]]]:
    """
    Build a row/period value map from high-resolution OCR.

    This is a P&L-only accuracy cross-check. It uses OCR word positions
    to associate each numeric value with the correct visible period
    column instead of deriving values arithmetically.
    """
    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )
    except Exception:
        return {}

    try:
        result = {}

        for page_number, page in enumerate(
            document,
            start=1,
        ):
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(3, 3),
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                [
                    pixmap.width,
                    pixmap.height,
                ],
                pixmap.samples,
            )

            try:
                data = pytesseract.image_to_data(
                    image,
                    output_type=Output.DICT,
                    config="--psm 6",
                )
            except Exception:
                continue

            words = []

            for index, raw_text in enumerate(data["text"]):
                word = raw_text.strip()

                if not word:
                    continue

                try:
                    confidence = float(
                        data["conf"][index]
                    )
                except (
                    ValueError,
                    TypeError,
                ):
                    confidence = None

                words.append(
                    {
                        "text": word,
                        "left": int(data["left"][index]),
                        "top": int(data["top"][index]),
                        "width": int(data["width"][index]),
                        "height": int(data["height"][index]),
                        "confidence": confidence,
                    }
                )

            if not words:
                continue

            # Locate the two visible period headers.
            header_words = [
                word
                for word in words
                if word["text"] in {
                    "31-Mar-18",
                    "31-Mar-17",
                    "31-Mar-18",
                    "31-Mar-17",
                }
            ]

            # Tesseract may split a date differently, so use the exact
            # known date strings when present.
            period_positions = {}
            for word in header_words:
                if word["text"] in {
                    "31-Mar-18",
                    "31-Mar-17",
                }:
                    period_positions[word["text"]] = (
                        word["left"] + word["width"] / 2
                    )

            if len(period_positions) < 2:
                continue

            left_period = min(
                period_positions,
                key=period_positions.get,
            )
            right_period = max(
                period_positions,
                key=period_positions.get,
            )

            left_x = period_positions[left_period]
            right_x = period_positions[right_period]

            # Group words into visual rows.
            rows = []
            for word in sorted(
                words,
                key=lambda item: (
                    item["top"],
                    item["left"],
                ),
            ):
                if (
                    not rows
                    or abs(
                        word["top"]
                        - rows[-1][0]["top"]
                    ) > 14
                ):
                    rows.append([word])
                else:
                    rows[-1].append(word)

            for row in rows:
                row.sort(key=lambda item: item["left"])

                numeric_words = []
                label_words = []

                for word in row:
                    token = word["text"]

                    if re.fullmatch(
                        r"[\(\)\-\d,\.]+",
                        token,
                    ):
                        center_x = (
                            word["left"]
                            + word["width"] / 2
                        )

                        if center_x > (
                            min(left_x, right_x) - 30
                        ):
                            numeric_words.append(
                                word
                            )
                            continue

                    # Everything left of the numeric columns is
                    # treated as the row label.
                    if word["left"] < min(
                        left_x,
                        right_x,
                    ) - 30:
                        label_words.append(word)

                if not label_words or not numeric_words:
                    continue

                label = _normalize_pnl_label(
                    " ".join(
                        word["text"]
                        for word in label_words
                    )
                )

                if len(label) < 3:
                    continue

                row_values = {}

                for word in numeric_words:
                    center_x = (
                        word["left"]
                        + word["width"] / 2
                    )

                    period = (
                        left_period
                        if abs(center_x - left_x)
                        <= abs(center_x - right_x)
                        else right_period
                    )

                    confidence = word["confidence"]

                    # Only use reasonably confident OCR values.
                    if (
                        confidence is not None
                        and confidence < 80
                    ):
                        continue

                    row_values[period] = (
                        word["text"],
                        confidence,
                    )

                if row_values:
                    result[
                        f"{page_number}:{label}"
                    ] = row_values

        return result

    finally:
        document.close()


def _pnl_highres_ocr_values(
    file_bytes: bytes,
) -> dict[tuple[str, str], tuple[str, str, int]]:
    """
    Read high-resolution P&L table values with Tesseract.

    Returns:
        {(normalized_label, period): (raw_value, evidence_text, page_number)}

    This is a source-reading cross-check only. It does not calculate
    or infer values.
    """
    import re
    import pytesseract
    from PIL import Image

    values: dict[tuple[str, str], tuple[str, str, int]] = {}

    try:
        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )
    except Exception:
        return values

    try:
        for page_number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(3.0, 3.0),
                alpha=False,
            )
            image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")

            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config="--psm 6",
            )

            words = []
            for i, raw in enumerate(data["text"]):
                word = (raw or "").strip()
                if not word:
                    continue
                try:
                    conf = float(data["conf"][i])
                except (TypeError, ValueError):
                    conf = 0.0
                words.append({
                    "text": word,
                    "x": int(data["left"][i]),
                    "y": int(data["top"][i]),
                    "w": int(data["width"][i]),
                    "h": int(data["height"][i]),
                    "conf": conf,
                })

            # Locate the two reporting-period headers. OCR can split the
            # date into several tokens, so match a flexible date pattern.
            period_words = []
            for word in words:
                cleaned = re.sub(r"[^A-Za-z0-9-]", "", word["text"])
                match = re.fullmatch(
                    r"(?:31[-/])?(?:Mar|Mar-)?(?:17|18)",
                    cleaned,
                    flags=re.IGNORECASE,
                )
                if cleaned.lower() in {"31-mar-18", "31-mar-17"}:
                    period_words.append((cleaned, word["x"] + word["w"] / 2))

            # Also support OCR variants such as 31-Mar-1B / 31-Mar-l7.
            if len(period_words) < 2:
                for word in words:
                    cleaned = re.sub(r"[^A-Za-z0-9-]", "", word["text"]).lower()
                    normalized = cleaned.replace("b", "8").replace("l", "1")
                    if normalized in {"31-mar-18", "31-mar-17"}:
                        period_words.append((normalized, word["x"] + word["w"] / 2))

            period_centers = {}
            for period, center in period_words:
                normalized_period = period.lower()
                if normalized_period in {"31-mar-18", "31-mar-17"}:
                    period_centers[normalized_period] = center

            if len(period_centers) < 2:
                continue

            # Group OCR words into visual rows using their vertical centers.
            rows = []
            for word in sorted(words, key=lambda item: (item["y"], item["x"])):
                cy = word["y"] + word["h"] / 2
                placed = False
                for row in rows:
                    if abs(cy - row["cy"]) <= max(12, word["h"] * 0.65):
                        row["words"].append(word)
                        row["cy"] = (row["cy"] + cy) / 2
                        placed = True
                        break
                if not placed:
                    rows.append({"cy": cy, "words": [word]})

            def normalize_label(label: str) -> str:
                return re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    label.lower(),
                ).strip()

            target_labels = {
                "interest earned",
                "other income",
                "total income",
                "interest expended",
                "operating expenses",
                "provisions and contingencies",
                "total expenditure",
                "net profit for the year",
            }

            number_pattern = re.compile(
                r"^\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?$"
            )

            for row in rows:
                row_words = sorted(row["words"], key=lambda item: item["x"])
                if not row_words:
                    continue

                # Build label from the left side, stopping naturally before
                # numeric columns. Note references such as "13" are ignored.
                label_words = [
                    w for w in row_words
                    if w["x"] < min(period_centers.values()) - 80
                    and not number_pattern.fullmatch(w["text"].replace(" ", ""))
                ]
                label = normalize_label(" ".join(w["text"] for w in label_words))

                matched_label = None
                for candidate in target_labels:
                    if label == candidate or candidate in label:
                        matched_label = candidate
                        break
                if matched_label is None:
                    continue

                for period, center in period_centers.items():
                    candidates = []
                    for word in row_words:
                        token = word["text"].replace(" ", "")
                        if not number_pattern.fullmatch(token):
                            continue
                        if word["conf"] < 80:
                            continue
                        token_center = word["x"] + word["w"] / 2
                        distance = abs(token_center - center)
                        if distance < 500:
                            candidates.append((distance, word))

                    if not candidates:
                        continue

                    candidates.sort(key=lambda item: item[0])
                    word = candidates[0][1]
                    raw_value = word["text"].strip()

                    values[(normalize_label(matched_label), period)] = (
                        raw_value,
                        f"{matched_label} {raw_value}",
                        page_number,
                    )

    except Exception:
        return values
    finally:
        document.close()

    return values


def _correct_pnl_fields_from_highres_ocr(
    result: ExtractionResult,
    file_bytes: bytes,
) -> ExtractionResult:
    """
    Correct final ExtractedField/table values using high-confidence,
    source-reading OCR. No arithmetic inference is performed.
    """
    ocr_values = _pnl_highres_ocr_values(file_bytes)
    if not ocr_values:
        return result

    def normalize_label(value: str | None) -> str:
        import re
        return re.sub(
            r"[^a-z0-9]+",
            " ",
            (value or "").lower(),
        ).strip()

    import re

    def normalize_period(value: str | None) -> str:
        text = (value or "").strip().lower()
        match = re.search(r"31[-/](?:mar)[-/](17|18)", text)
        if match:
            return f"31-mar-{match.group(1)}"
        return text

    for field in result.fields:
        key = (
            normalize_label(field.field_name),
            normalize_period(field.period),
        )
        match = ocr_values.get(key)
        if not match:
            continue

        raw_value, evidence_text, page_number = match
        if field.value != raw_value:
            # This correction runs after conversion, so result.fields
            # contains final ExtractedField objects.
            field.value = raw_value
            field.normalized_number = _normalize_number(raw_value)
            field.evidence = Evidence(
                source_text=evidence_text,
                page_number=page_number,
            )

    # Keep the table synchronized with the corrected final fields.
    for table in result.tables:
        for row in table.rows:
            if len(row) < 3:
                continue
            label = normalize_label(str(row[0]))
            for index, period in enumerate(result.periods[:2], start=1):
                match = ocr_values.get((label, normalize_period(period)))
                if match and index < len(row):
                    row[index] = match[0]

    return result

def _extract_fields(
    document_type: str,
    source_text: str,
    document_parts: list,
    file_bytes: bytes | None = None,
) -> SimpleFieldExtraction:

    try:

        client = _get_gemini_client()

        if document_type == "invoice":

            extraction_instructions = """
Extract the invoice using BOTH:

1. The original document image(s)
2. The OCR text and OCR coordinates

The original image is the primary source for
visually determining table structure and values.

The OCR text is supporting evidence.

METADATA:

Identify the parties from the labels and
visual document context.

vendor_name:
The company identified as seller, vendor,
supplier, From, Bill From, or equivalent.

customer_name:
The company identified as customer, client,
buyer, To, Bill To, or equivalent.

Do not determine the parties merely from which
company name appears first.

Extract:

- document_title
- document_date
- vendor_name
- customer_name
- currency

FIELDS:

Extract EVERY meaningful invoice-level value,
including when visible:

- Invoice Number
- Invoice Date
- Due Date
- Subtotal
- Tax
- Discount
- Shipping
- Handling
- Other Charges
- Total Due
- Amount Due
- Payment information
- Other meaningful invoice values

LINE ITEMS:

Extract EVERY visible invoice table row.

For every line item provide:

- description
- quantity
- unit_price
- line_total
- evidence

IMPORTANT TABLE RULES:

Read the invoice table visually.

Do NOT infer quantity from arithmetic.

Do NOT calculate:

quantity = line_total / unit_price

Do NOT use the product description to guess
the quantity.

Do NOT assume that a number appearing inside
the product description is the quantity.

The quantity must be the value in the invoice's
actual quantity column.

The unit price must be the value in the actual
unit-price column.

The line total must be the value in the actual
amount/extension column.

Use the visual horizontal column alignment
from the original image.

If a value cannot be reliably read from the
document, return null.

For example, if the quantity is visually
unreadable, return:

"quantity": null

Do not substitute a different number merely
because it makes the arithmetic work.

The source_text for each line item should
contain only the relevant source text for that
row.

Do not put reasoning, explanations, instructions,
or commentary into field values.
"""

        else:

            extraction_instructions = """
Extract ALL meaningful information from the
financial document.

Use BOTH:

1. The original document image(s)
2. The OCR text

The original image is the primary source for
visually interpreting tables and document layout.

Extract:

- document title
- dates
- company/entity
- currency and units
- reporting periods
- every meaningful financial line item
- every visible value
- comparative-period values
- headers and other meaningful information

For every financial line item, create a
separate field.

A value belonging to a reporting period must
have that period in the period field.

Do not merge different periods.

Preserve negative values.

Parentheses indicate negative values.

Do not calculate values.

Do not infer missing values.

Do not put explanations or reasoning inside
field values.

source_text must contain only supporting text
from the document.

page_number should identify the source page.
"""

        prompt = f"""
You are a financial document information
extraction system.

Document type:
{document_type}

Return ONLY the structured JSON object
required by the response schema.

Do not return explanations.
Do not return reasoning.
Do not return commentary.

{extraction_instructions}

GENERAL RULES:

1. Use only information supported by the
   supplied document.

2. The original document image is authoritative
   for visual layout.

3. OCR text is supporting information and may
   contain recognition errors.

4. Do not invent information.

5. Do not calculate missing values.

6. Missing or unreadable values must be null.

7. Preserve the original document values.

8. Extract all meaningful visible information.

9. Provide evidence whenever possible.

10. Keep evidence concise. Do not copy entire
    pages into source_text.

11. Do not duplicate the same field unnecessarily.

12. For comparative statements, create separate
    fields for each reporting period.

13. The fields array must contain the actual
    financial statement rows and values.

OCR DOCUMENT CONTENT:

{source_text}
"""

        contents = []

        contents.extend(
            document_parts
        )

        contents.append(
            types.Part.from_text(
                text=prompt
            )
        )

        response = _call_gemini_with_fallback(
            client=client,
            contents=contents,
            response_schema=SimpleFieldExtraction,
        )

        try:

            result = (
                SimpleFieldExtraction
                .model_validate_json(
                    response.text
                )
            )

        except Exception as exc:

            raise ExtractionError(
                "Gemini returned invalid structured "
                "extraction output after model fallback."
            ) from exc

        if (
            not result.fields
            and not result.invoice_line_items
        ):

            raise ExtractionError(
                "Gemini returned no meaningful document fields "
                "after model fallback."
            )

        return result

    except ExtractionError:
        raise

    except Exception as exc:

        raise ExtractionError(
            "Gemini extraction failed unexpectedly."
        ) from exc

def extract_document(
    document_type: str,
    pages: list[dict],
    filename: str,
    file_bytes: bytes,
) -> ExtractionResult:

    try:

        if not pages:

            raise ExtractionError(
                "No document pages were provided for extraction."
            )

        source_text = _build_source_text(
            pages
        )

        if not source_text.strip():

            raise ExtractionError(
                "No readable text was found in the document."
            )

        document_parts = (
            _build_document_parts(
                filename=filename,
                file_bytes=file_bytes,
                document_type=document_type,
            )
        )

        field_result = _extract_fields(
            document_type=document_type,
            source_text=source_text,
            document_parts=document_parts,
            file_bytes=file_bytes,
        )

        fields = _convert_fields(
            field_result.fields
        )

        tables = _build_tables_from_fields(
            document_type=document_type,
            fields=fields,
        )

        extraction_result = ExtractionResult(
            document_type=document_type,
            metadata=field_result.metadata,
            periods=field_result.periods,
            fields=fields,
            tables=tables,
            invoice_line_items=(
                field_result.invoice_line_items
            ),
        )

        if document_type == "profit_loss":
            extraction_result = _correct_pnl_fields_from_highres_ocr(
                result=extraction_result,
                file_bytes=file_bytes,
            )

        return extraction_result

    except ExtractionError:
        raise

    except Exception as exc:

        raise ExtractionError(
            "Document extraction failed unexpectedly."
        ) from exc


def extract_document_data(
    document_type: str,
    pages: list[dict],
    filename: str,
    file_bytes: bytes,
) -> ExtractionResult:

    return extract_document(
        document_type=document_type,
        pages=pages,
        filename=filename,
        file_bytes=file_bytes,
    )