from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):

    __tablename__ = "documents"

    # --------------------------------------------------------
    # Primary key
    # --------------------------------------------------------

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # --------------------------------------------------------
    # Document information
    # --------------------------------------------------------

    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # --------------------------------------------------------
    # Processing status
    # --------------------------------------------------------

    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    # --------------------------------------------------------
    # Complete extraction result stored as JSON text
    # --------------------------------------------------------

    extraction_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------------
    # Financial validation result stored as JSON text
    # --------------------------------------------------------

    financial_validation_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------------
    # Error information, if processing fails
    # --------------------------------------------------------

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )