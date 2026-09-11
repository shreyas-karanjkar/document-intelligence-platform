# Document Intelligence Platform

Intelligent Document Extraction, Validation & API Platform built for the AI Engineer Intern Technical Case Study.

The platform accepts financial documents, extracts structured information using OCR/text extraction and Gemini-based AI extraction, validates financial relationships deterministically, stores processing results in PostgreSQL, and exposes the results through a REST API and web dashboard.

## Live Deployment

| Resource | URL |
|---|---|
| Live Application | https://document-intelligence-platform-hjzp.onrender.com |
| Swagger / OpenAPI | https://document-intelligence-platform-hjzp.onrender.com/docs |
| Health API | https://document-intelligence-platform-hjzp.onrender.com/api/v1/health |
| GitHub Repository | https://github.com/shreyas-karanjkar/document-intelligence-platform |

The Render free instance may spin down after inactivity, so the first request after a period of inactivity can take longer.

## Supported Documents

The platform supports four document categories:

- Invoice
- Balance Sheet
- Profit & Loss
- Cash Flow Statement

Supported file formats:

- PDF
- JPG / JPEG
- PNG

Maximum document size and page count are controlled through environment variables. The case-study configuration limits documents to 3 pages.

## Core Capabilities

### Document Validation

Before extraction, the application validates:

- Supported file type
- File size
- Empty/corrupt files
- PDF integrity
- Maximum page count
- Basic document readability

### OCR and Text Extraction

- PDF text is extracted using PyMuPDF.
- Image/scanned content is processed using Tesseract OCR.
- The production Docker image installs the Tesseract system dependency.
- Page-aware text is retained so extracted values can include evidence and page numbers.

### AI Extraction

Gemini is used to transform document content into structured extraction results.

The extraction workflow captures:

- Document metadata
- Dates and periods
- Currency
- Parties/entities
- Financial line items
- Comparative-period values
- Tables
- Invoice line items
- Source evidence
- Page numbers where available

Missing values are represented as null rather than being invented.

### Financial Validation

Validation is deterministic and separate from the AI extraction layer.

Examples include:

**Invoice**
- Quantity × unit price ≈ line total
- Line-item subtotal reconciliation
- Tax/total reconciliation

**Balance Sheet**
- Assets ≈ liabilities + equity
- Component-sum checks
- Independent validation for each period

**Profit & Loss**
- Income components ≈ total income
- Expense components ≈ total expenditure
- Comparative-period reconciliation

**Cash Flow**
- Operating + investing + financing + FX ≈ net change
- Opening cash + net change/adjustments ≈ closing cash

Each validation result contains the relevant formula/check, inputs, calculated value, reported value, variance and status.

Possible validation statuses:

- `PASS`
- `FAIL`
- `NOT_APPLICABLE`

If required inputs are missing, the system does not make assumptions and returns `NOT_APPLICABLE`.

## Architecture

```text
User / Browser
      |
      v
Frontend Dashboard
      |
      v
FastAPI REST API
      |
      +----------------------+
      |                      |
      v                      v
Document Validation     OCR / PDF Text Extraction
                             |
                             v
                       Gemini AI Extraction
                             |
                             v
                    Financial Validation
                             |
                             v
                      Structured JSON
                             |
                             v
                     Neon PostgreSQL
                             |
                             v
                    Dashboard / API
```

The detailed architecture diagram is available at:

`docs/architecture.png`

## Technology Stack

### Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Uvicorn

### Document Processing

- PyMuPDF
- Pillow
- Tesseract OCR

### AI

- Google Gemini
- Structured extraction workflow
- Model fallback handling

### Database

- PostgreSQL
- Neon
- SQLAlchemy ORM

### Frontend

- HTML
- CSS
- JavaScript

### Deployment

- Docker
- Render Web Service
- Neon PostgreSQL

### API Documentation

- FastAPI Swagger / OpenAPI

## Repository Structure

```text
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/routes/documents.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   ├── pytest.ini
│   └── requirements.txt
│
├── frontend/
│   ├── templates/
│   └── static/
│
├── docs/
│   ├── architecture.png
│   ├── solution_presentation.pptx
│   ├── solution_presentation.pdf
│   └── screenshots/
│
├── sample_outputs/
│   └── profit_loss_2018.json
│
├── test_documents/
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

## API

### Health Check

```http
GET /api/v1/health
```

Returns the health/status of the deployed application.

### Process Document

```http
POST /api/v1/documents/process
```

Processes an uploaded document and returns the structured extraction and financial validation result.

The request contains the selected document type and uploaded document.

### List Processed Documents

```http
GET /api/v1/documents
```

Returns processing history stored in the database.

### Retrieve a Document Result

```http
GET /api/v1/documents/{document_name}
```

Retrieves the latest stored processing result for a document name.

Interactive request/response examples are available through the deployed Swagger UI:

https://document-intelligence-platform-hjzp.onrender.com/docs

## Persistence

Processing results are stored in Neon PostgreSQL.

The application uses SQLAlchemy and creates the required database table during application startup.

Persistence enables:

- Processing history
- Retrieval by document name
- Dashboard history display
- Reuse of previously processed results

## Configuration

Configuration is externalized through environment variables.

Example:

```env
APP_NAME=Document Intelligence Platform
ENVIRONMENT=production

DATABASE_URL=<postgresql connection string>

GEMINI_API_KEY=<gemini api key>
GEMINI_MODEL=gemini-3.6-flash

FINANCIAL_TOLERANCE=0.01

MAX_FILE_SIZE_MB=10
MAX_PAGES=3
```

Never commit `.env` or real credentials.

`.env.example` is included as a safe configuration template.

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/shreyas-karanjkar/document-intelligence-platform.git
cd document-intelligence-platform
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install backend dependencies

```powershell
pip install -r backend\requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root using `.env.example` as the template.

Provide:

- PostgreSQL `DATABASE_URL`
- Gemini API key
- Required application configuration

### 5. Start the application

From the `backend` directory:

```powershell
cd backend
uvicorn app.main:app --reload
```

The local dashboard is served by FastAPI and the API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Testing

The project includes automated tests covering:

- File validation
- OCR/document handling
- Extraction schema
- Financial calculations
- Database operations
- Document service flow
- API-related behavior

Latest local test result:

```text
18 passed
3 skipped
1 warning
```

The skipped tests are direct Gemini API tests that were skipped after the free-tier Gemini quota was exhausted. The application's extraction service includes fallback handling for model availability/quota failures.

## Sample Output

A real production-generated Profit & Loss result is included in:

```text
sample_outputs/profit_loss_2018.json
```

The sample demonstrates structured extraction and financial validation output.

## Production Verification

The deployed application was verified with a real Profit & Loss document:

```text
Consolidated Profit & Loss 2018.pdf
```

The production flow successfully demonstrated:

1. Document upload
2. PDF processing
3. AI extraction
4. Structured field extraction
5. Table extraction
6. Financial validation
7. PASS processing status
8. PostgreSQL persistence
9. Processing history
10. Retrieval of the saved result through the API

## Error / Failure Handling

The application handles errors across multiple layers, including:

- Invalid or unsupported files
- Empty/corrupt documents
- Page-count violations
- OCR/extraction failures
- AI/model failures
- Database failures
- Unexpected application exceptions

Errors are logged and returned using appropriate API error responses.

## Security

- API keys are stored through environment variables.
- `.env` is excluded from Git.
- Database credentials are not committed.
- `.env.example` contains placeholders only.
- The application does not hardcode secrets.

## Limitations

- AI extraction depends on external Gemini model availability and quota.
- The case-study implementation limits documents to 3 pages.
- Very complex layouts or poor-quality scans may reduce extraction accuracy.
- The free Render instance can sleep after inactivity, causing cold-start latency.
- The current application does not implement user authentication or role-based access control.
- The current synchronous processing model is suitable for the case study but is not ideal for long-running production workloads.

## Production Improvements

For a larger production deployment, the following improvements would be appropriate:

- Asynchronous document-processing jobs
- Queue-based OCR/LLM processing
- Stronger multi-provider AI fallback
- Retry with exponential backoff
- Object storage for original documents
- Authentication and authorization
- Rate limiting
- Monitoring and metrics
- Distributed tracing
- Database migrations
- Document/version management
- Better OCR preprocessing for low-quality scans
- Human review workflows for low-confidence extraction
- Larger-scale automated evaluation datasets

## AI Coding Assistant Declaration

AI assistance was used during development.

ChatGPT was used for:

- Code generation
- Debugging
- Architecture guidance
- Test development/support
- Documentation drafting
- Deployment troubleshooting

Generated code was reviewed, executed, tested and modified as necessary. The final implementation was validated through automated tests and live production verification.

## Presentation

The technical case-study presentation is available in:

```text
docs/solution_presentation.pptx
docs/solution_presentation.pdf
```

The presentation covers the architecture, implementation, extraction workflow, validation strategy, production deployment, testing, limitations and AI-assisted development declaration.
