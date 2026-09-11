FROM python:3.11-slim

# Install Tesseract OCR
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Application root
WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application
COPY backend /app/backend
COPY frontend /app/frontend

# Run from backend so "app" is importable
WORKDIR /app/backend

# Render provides the PORT environment variable
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}