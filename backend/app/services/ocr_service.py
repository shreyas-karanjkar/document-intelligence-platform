from io import BytesIO
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import Output


class OCRExtractionError(Exception):
    """Raised when document text extraction or OCR fails."""


def _extract_ocr_layout(
    image: Image.Image,
) -> tuple[str, list[dict]]:

    try:

        data = pytesseract.image_to_data(
            image,
            output_type=Output.DICT,
        )

    except pytesseract.TesseractNotFoundError as exc:

        raise OCRExtractionError(
            "Tesseract OCR executable was not found."
        ) from exc

    except Exception as exc:

        raise OCRExtractionError(
            "OCR layout extraction failed."
        ) from exc

    words = []

    for index, text in enumerate(
        data["text"]
    ):

        text = text.strip()

        if not text:
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
                "text": text,
                "left": data["left"][index],
                "top": data["top"][index],
                "width": data["width"][index],
                "height": data["height"][index],
                "confidence": confidence,
            }
        )

    # Reconstruct readable text in approximate
    # reading order.
    sorted_words = sorted(
        words,
        key=lambda word: (
            word["top"],
            word["left"],
        ),
    )

    lines = []

    current_line = []
    current_top = None

    for word in sorted_words:

        top = word["top"]

        if (
            current_top is None
            or abs(top - current_top) <= 10
        ):

            current_line.append(word)

            if current_top is None:
                current_top = top

        else:

            current_line.sort(
                key=lambda item: item["left"]
            )

            lines.append(
                " ".join(
                    item["text"]
                    for item in current_line
                )
            )

            current_line = [word]
            current_top = top

    if current_line:

        current_line.sort(
            key=lambda item: item["left"]
        )

        lines.append(
            " ".join(
                item["text"]
                for item in current_line
            )
        )

    text = "\n".join(lines).strip()

    return text, words


def extract_text_from_native_pdf(
    file_bytes: bytes,
) -> list[dict]:

    try:

        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )

    except Exception as exc:

        raise OCRExtractionError(
            "Unable to open PDF for text extraction."
        ) from exc

    pages = []

    try:

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            text = page.get_text(
                "text"
            ).strip()

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "source": "native_pdf",
                }
            )

    except Exception as exc:

        raise OCRExtractionError(
            "Failed while extracting text from PDF."
        ) from exc

    finally:

        document.close()

    return pages


def extract_text_from_image(
    image: Image.Image,
    page_number: int = 1,
) -> dict:

    try:

        text, layout = _extract_ocr_layout(
            image
        )

    except OCRExtractionError:
        raise

    except Exception as exc:

        raise OCRExtractionError(
            "OCR processing failed."
        ) from exc

    return {
        "page_number": page_number,
        "text": text,
        "source": "ocr",
        "layout": layout,
    }


def extract_text_from_scanned_pdf(
    file_bytes: bytes,
) -> list[dict]:

    try:

        document = pymupdf.open(
            stream=file_bytes,
            filetype="pdf",
        )

    except Exception as exc:

        raise OCRExtractionError(
            "Unable to open scanned PDF for OCR."
        ) from exc

    pages = []

    try:

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            pixmap = page.get_pixmap(
                matrix=pymupdf.Matrix(
                    2,
                    2,
                )
            )

            image = Image.frombytes(
                "RGB",
                [
                    pixmap.width,
                    pixmap.height,
                ],
                pixmap.samples,
            )

            page_result = (
                extract_text_from_image(
                    image=image,
                    page_number=page_number,
                )
            )

            pages.append(
                page_result
            )

    except OCRExtractionError:
        raise

    except Exception as exc:

        raise OCRExtractionError(
            "Failed while processing scanned PDF."
        ) from exc

    finally:

        document.close()

    return pages


def extract_text_from_uploaded_document(
    filename: str,
    file_bytes: bytes,
) -> list[dict]:

    extension = Path(
        filename
    ).suffix.lower()

    if extension == ".pdf":

        native_pages = (
            extract_text_from_native_pdf(
                file_bytes
            )
        )

        has_meaningful_text = any(
            page["text"].strip()
            for page in native_pages
        )

        if has_meaningful_text:

            return native_pages

        return extract_text_from_scanned_pdf(
            file_bytes
        )

    if extension in {
        ".jpg",
        ".jpeg",
        ".png",
    }:

        try:

            image = Image.open(
                BytesIO(file_bytes)
            )

            image.load()

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:

            raise OCRExtractionError(
                "Unable to open image for OCR."
            ) from exc

        return [
            extract_text_from_image(
                image=image,
                page_number=1,
            )
        ]

    raise OCRExtractionError(
        "Unsupported document type for text extraction."
    )