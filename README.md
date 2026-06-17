# Label Verification App

AI-powered app for verifying that labels on alcoholic beverages meet federal requirements. Users upload images of bottle labels and PDFs of label application forms and receive a compliance check covering brand name, alcohol content, and the government warning text.

## General Approach
My goal was to build a full-stack app with a simple user-friendly interface that allows users to: 

1) upload images and pdf forms; 
2) receive a downloadable file with the extracted data and the results of the data validations. 

To accomplish this, I chose NextJS for the front end because of its convenience features integrating React and Tailwind CSS. I then built out the backend with Python because of its robust data and LLM-related libraries. In order to create a framework for persistent data, I also chose to use SQLite to store the results of data extractions. For the LLM, I used Qwen 3.5-2B for its multi-modal performance, its relative light weight, and OpenAI API compatability for ease of use. The LLM is hosted remotely by Modal.

Assumptions made here include that users would upload images and pdf applications separately. Future improvements would allow for batch uploads of folders. Currently, the app does not include branch logic for the different requirements of malt beverages, distilled spirits, and wines. Future improvements would account for these differences. Additionally, future improvements would allow for additonal visual validations including label placement, font size, capitalizations, etc. 

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 |
| Backend | FastAPI, Python 3.13 |
| Database | SQLite (via SQLModel) |
| LLM (production) | Qwen/Qwen3.5-2B on Modal (vLLM) |
| LLM (local dev) | mlx-community/Qwen3.5-2B-OptiQ-4bit via mlx-lm |

---

## Running Locally

You need three things running: the local LLM server (or use the live Modal endpoint), the FastAPI backend, and the Next.js frontend.

### Prerequisites

- [pnpm](https://pnpm.io/installation)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.13
- An Apple Silicon Mac for local LLM inference (mlx-lm), or use the live Modal endpoint instead

### 1. Install dependencies

```bash
# Python backend
uv sync

# Node frontend
pnpm install
```

### 2. Configure environment

**Backend** — create `backend/.env`:
```
HF_TOKEN=your_huggingface_token
```

**Frontend** — `.env.local` is already present at the project root:
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 3. Start the LLM server

**Option A — Local (Apple Silicon, uses mlx-vlm):**
```bash
uv run python -m mlx_vlm.server --model mlx-community/Qwen3.5-2B-OptiQ-4bit --port 8080
```
Then set `MODAL_API_URL=http://localhost:8080/v1` in `backend/.env`.

**Option B — Live Modal endpoint (no local GPU needed):**
The backend defaults to the deployed Modal endpoint automatically. No extra step needed.

### 4. Start the FastAPI backend

```bash
uv run uvicorn backend.main:app --reload --port 8000
```

The backend will create `label_verification.db` (SQLite) in the project root on first run.

Available endpoints:
- `GET  /health` — health check
- `POST /verify` — run a label verification
- `GET  /export` — download all past runs as CSV

### 5. Start the Next.js frontend

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## Running Tests

### Frontend (Vitest + Testing Library)

```bash
pnpm test
```

Runs 52 unit and component tests covering `dedupeFiles`, `formatBytes`, `isVerificationResult`, file upload state, the verify flow, error handling, and CSV download.

### Backend (pytest)

**Unit + integration-free tests** (safe to run anytime, no LLM needed):
```bash
uv run pytest -m "not integration"
```

Runs 103 tests across schemas, deterministic validation logic, database setup, and all three API routes. Routes use an in-memory SQLite database — the real `label_verification.db` is never touched.

**Integration tests** (requires the live Modal endpoint to be active):
```bash
uv run pytest -m integration
```

Runs 4 tests that call the deployed Modal LLM using the real label images and PDF form in `backend/public/spirit/`. Confirms end-to-end extraction from both image and PDF inputs.

**All tests:**
```bash
uv run pytest
```

### Test assets

Sample label images and approval form used by the integration tests:
```
backend/public/spirit/
├── spirit front.jpeg
├── spirit back.jpeg
└── spirit form.pdf
```

---

## Deploying the LLM to Modal

The Modal service is defined in `backend/services/modal_service.py`. To deploy:

```bash
uv run modal deploy backend/services/modal_service.py
```

The deployed endpoint URL goes in `backend/.env` as `MODAL_API_URL`.

---

## Project Structure

```
├── app/                    # Next.js app (App Router)
│   └── chat/page.tsx       # Main upload + verification UI
├── backend/
│   ├── main.py             # FastAPI app, routes
│   ├── schemas.py          # Pydantic models (BeverageInfo, FormInfo, DataCheck)
│   ├── models.py           # SQLModel table (VerificationRun)
│   ├── database.py         # SQLite engine + session
│   ├── config/main.py      # App settings (pydantic-settings)
│   └── services/
│       ├── llm_service.py  # Image/PDF extraction + deterministic validation
│       └── modal_service.py # Modal vLLM deployment
├── pyproject.toml          # Python dependencies (managed by uv)
└── package.json            # Node dependencies (managed by pnpm)
```
