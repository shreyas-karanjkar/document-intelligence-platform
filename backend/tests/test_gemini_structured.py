import pytest
from google import genai

from app.core.config import settings
from app.schemas.extraction import ExtractionResult


class SimpleExtraction(ExtractionResult):
    pass


def test_gemini_structured_output():
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = client.interactions.create(
            model=settings.gemini_model,
            input="""
            Extract the following information:

            Document type: Cash Flow Statement
            Title: Consolidated Cash Flow Statement
            Currency: INR crore
            """,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": SimpleExtraction.model_json_schema(),
            },
        )
    except Exception as exc:
        if "429" in str(exc) or "quota" in str(exc).lower():
            pytest.skip("Gemini API quota is currently exhausted")
        raise

    assert response is not None