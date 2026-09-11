import pytest
from google import genai

from app.core.config import settings


def test_gemini_connection():
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents="Reply with exactly: Gemini connection successful",
        )
    except Exception as exc:
        if "429" in str(exc) or "quota" in str(exc).lower():
            pytest.skip("Gemini API quota is currently exhausted")
        raise

    assert response is not None
    assert response.text is not None
    assert "Gemini connection successful" in response.text