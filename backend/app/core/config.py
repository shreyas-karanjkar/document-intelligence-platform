from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "Document Intelligence Platform"
    environment: str = "development"

    database_url: str = "sqlite:///./document_intelligence.db"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.7-flash"

    financial_tolerance: float = 0.01

    max_file_size_mb: int = 10
    max_pages: int = 3

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()