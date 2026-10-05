# Ledger — Intelligent Business Document Analysis

AI-powered analysis for invoices, contracts, financial reports, and compliance
documents. Every extracted figure, deadline, and anomaly is traceable back to
the exact page and line it came from.

## 1. Overview

Upload an invoice, contract, financial report, or compliance document (PDF,
PNG, or JPG — including scanned pages) and the system will:

- Classify the document type
- Extract structured fields (amounts, dates, parties, clauses)
- Detect deadlines and obligations
- Validate financial totals deterministically (never trusting an LLM with
  arithmetic)
- Flag anomalies — both rule-based (duplicate line items, bad totals) and
  AI-detected (conflicting clauses, unusual language)
- Flag missing required fields
- Let you click any finding and jump straight to the source page, with the
  supporting text shown alongside it
- Answer questions about a document, grounded only in its own content

## 2. Architecture

```
intelligent-document-ai/
├── frontend/    Next.js 14 (App Router) + TypeScript + Tailwind
├── backend/     FastAPI + SQLAlchemy + Postgres
```

**Pipeline:** upload → validate → store → extract text (PyMuPDF) → OCR
fallback for scanned pages (PaddleOCR) → classify → extract (LLM, schema-
validated with Pydantic) → deterministic financial validation (plain Python)
→ AI + rule-based anomaly detection → missing-field detection → evidence
mapping → summarize → done.

**AI provider abstraction:** all AI calls go through `AIProvider`
(`app/ai/providers/base.py`). `OpenAIProvider` talks to OpenAI and does all
real analysis — extraction, classification, anomaly detection, chat, and
summarization all hit the live API. A new provider (Anthropic, Google, a
local model) can be added without touching any business logic — just
implement `AIProvider` and register it in `app/ai/router.py`. Without
`OPENAI_API_KEY` set, document analysis fails fast with a clear error
(surfaced on the document as `status: failed`) rather than silently
faking a result.

Model *names* are never hard-coded — only task → tier routing
(`classification`/`extraction`/`reasoning`/... → `fast`/`primary`/
`reasoning`), configured via `OPENAI_DEFAULT_MODEL`, `OPENAI_FAST_MODEL`,
`OPENAI_REASONING_MODEL`.

## 3. Features

- Drag-and-drop upload with per-file progress, retry, and validation
- Live processing status (uploading → extracting text → analyzing →
  validating → completed)
- Dashboard with severity/type charts and a recent-documents table
- Document detail page with tabs: Overview, Deadlines, Obligations,
  Financial, Anomalies, Missing Data, Ask this document
- Split-screen evidence viewer — click any finding to see the source page
- "Ask this document" chat, answers grounded only in that document
- Cross-document Alerts view
- **Light/dark theme**, toggleable from the sidebar or Settings, persisted
  per browser (`localStorage`), with no flash of the wrong theme on load
- **AI model settings**, editable from Settings → AI model: choose the
  model name for each tier (default/fast/reasoning). Changes apply
  immediately, no restart — see "AI provider abstraction" below for how.
  The API key itself stays server-side only.
- Responsive from 320px phones to widescreen desktops

## 4. Tech stack

**Frontend:** Next.js, React, TypeScript, Tailwind CSS, Recharts, Lucide
icons.
**Backend:** Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL.
**Document processing:** PyMuPDF (text + page rendering), PaddleOCR
([github.com/PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)), Pillow.
**AI:** OpenAI API via a provider abstraction (see above). A valid
`OPENAI_API_KEY` is required for document analysis.

## 5. Installation

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- OCR runs on [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) 3.x with
  PaddlePaddle, installed via `pip install -r requirements.txt`. On first OCR
  call it downloads its detection/recognition models and caches them under
  `~/.paddlex` (network access is needed once). CPU is the default; GPU
  deployments need a compatible PaddlePaddle GPU build and
  `PADDLEOCR_DEVICE=gpu:0`.

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit values
uvicorn app.main:app --reload
```

The API is at `http://localhost:8000`; tables are created automatically on
startup (swap for Alembic migrations in production — see `app/models/` for
the schema).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```

The app is at `http://localhost:3000`.

## 6. Environment variables

See `.env.example` at the repo root for the backend, and
`frontend/.env.example` for the frontend. Key ones:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=                # required — document analysis fails without it
OPENAI_DEFAULT_MODEL=gpt-4o
OPENAI_FAST_MODEL=gpt-4o-mini
OPENAI_REASONING_MODEL=gpt-4o

DATABASE_URL=postgresql+psycopg2://docai:docai@localhost:5432/docai
JWT_SECRET=change-me-in-production

STORAGE_PATH=./storage
MAX_FILE_SIZE=26214400
```

## 7. Database setup

Install and start PostgreSQL locally, then create a database matching
`DATABASE_URL` in `.env`. Tables are created on app startup via
`Base.metadata.create_all`. For a real deployment, replace this with Alembic
migrations (scaffolding for this is straightforward to add under
`backend/alembic/`).

## 8. Testing

```bash
cd backend
pip install pytest httpx
pytest tests/ -v
```

Covers deterministic financial validation, missing-field detection, and core
API auth/access-control flows (none of these hit the AI provider, so no
API key is needed to run the suite). The full pipeline (upload → OCR →
extraction → anomaly detection → dashboard → chat) has been manually
verified end-to-end against a live server with a real `OPENAI_API_KEY`.

**Not yet included** (flagged honestly rather than faked): frontend
component tests, a Playwright/Cypress E2E suite, and contract/financial-
report/compliance extraction test fixtures — invoices are the fully wired
reference implementation; the other document types share the same pipeline
and prompts but have less test coverage.

## 9. Production deployment notes

- Swap `BackgroundTasks` in `app/api/documents.py` for a real task queue
  (Celery/RQ) so processing survives a server restart and can scale
  independently.
- Replace `Base.metadata.create_all` with Alembic migrations.
- Tighten CORS `allow_origins` in `app/main.py` to your real frontend origin.
- Add object storage (S3-compatible) instead of local disk for
  `STORAGE_PATH` if running more than one backend instance.
- Wire real per-model token pricing into `AIModelLog` cost tracking (a
  usage/cost admin view is a natural next page to add).

## 10. Security notes

- Passwords hashed with bcrypt; JWT bearer auth (`JWT_SECRET`,
  `JWT_EXPIRE_MINUTES`).
- Every document/finding query is scoped to `owner_id` — users can only ever
  see their own documents.
- File type and size are validated server-side on upload.
- Unhandled exceptions are caught globally and never leak stack traces to
  the client; full details are logged server-side.
- API keys are read from environment variables only and are never sent to
  the frontend.
- Basic rate limiting via `slowapi` (120 req/min per IP by default).
- `PUT /api/settings/ai-models` (provider/model choice) is currently open to
  any authenticated user, not gated to admins — fine for a single-tenant
  demo, but restrict it to `role == "admin"` before running this with
  multiple users who shouldn't be able to change each other's AI config.

## 12. Future improvements

- Vector/semantic search over `document_chunks` (the schema already has an
  `embedding` column ready for it)
- Resolve relative deadlines ("30 days from invoice receipt") into absolute
  calendar dates once a reference date is confirmed
- Precise bounding-box highlighting on the evidence page image (currently
  shows the source text as a callout beneath the page)
- Admin AI usage/cost dashboard (data is already logged in `ai_model_logs`)
- Contract/financial-report/compliance extraction parity with the invoice
  flow (schemas and prompts exist; deterministic validation and demo
  fixtures are invoice-only so far)
