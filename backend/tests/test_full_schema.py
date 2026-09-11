import pytest
from google import genai

from app.core.config import settings
from app.schemas.extraction import ExtractionResult


def test_full_extraction_schema():
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = client.interactions.create(
            model=settings.gemini_model,
            input="""
            Extract this short financial document.

            Document:
            Consolidated Cash Flow Statement

            Currency:
            INR crore

            Periods:
            March 31, 2022
            March 31, 2021

            Net cash flow from operating activities:
            (11,959.57) for March 31, 2022
            42,476.45 for March 31, 2021

            Net cash flow from investing activities:
            (2,216.33) for March 31, 2022
            (1,680.87) for March 31, 2021

            Net cash flow from financing activities:
            48,124.02 for March 31, 2022
            (7,321.35) for March 31, 2021

            Net increase in cash:
            34,113.22 for March 31, 2022
            33,332.40 for March 31, 2021
            """,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ExtractionResult.model_json_schema(),
            },
            generation_config={
                "max_output_tokens": 12000,
                "thinking_level": "low",
            },
        )
    except Exception as exc:
        if "429" in str(exc) or "quota" in str(exc).lower():
            pytest.skip("Gemini API quota is currently exhausted")
        raise

    assert response is not None
    assert response.output_text is not None