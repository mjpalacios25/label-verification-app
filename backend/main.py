import csv
import io
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from sqlmodel import Session, select

from .config.main import settings
from .database import create_db_and_tables, get_session
from .models import VerificationRun
from .schemas import DataCheck
from .services.llm_service import (
    extract_from_image,
    extract_structured_data_pdf,
    validate_results,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    if not settings.MODAL_API_URL:
        raise RuntimeError("MODAL_API_URL is not set — check backend/.env")
    if not settings.MODAL_API_URL.rstrip("/").endswith("/v1"):
        raise RuntimeError(f"MODAL_API_URL must end with /v1, got: {settings.MODAL_API_URL!r}")

    models_url = settings.MODAL_API_URL.rstrip("/").removesuffix("/v1") + "/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(models_url)
            resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(
            f"LLM endpoint unreachable at {settings.MODAL_API_URL!r}. "
            f"Run: uv run mlx_lm.server --model {settings.MODEL_NAME!r} --port 8080  "
            f"or point MODAL_API_URL at the Modal endpoint in backend/.env. Error: {exc}"
        ) from exc

    app.state.llm_client = OpenAI(
        base_url=settings.MODAL_API_URL,
        api_key=settings.MODAL_API_KEY or "none-needed",
    )
    yield

app = FastAPI(title="Label Verification API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


def _get_llm_client(request: Request) -> OpenAI:
    return request.app.state.llm_client


@app.post("/verify", response_model=DataCheck)
def verify(
    images: list[UploadFile] = File(...),
    form: UploadFile = File(...),
    session: Session = Depends(get_session),
    client: OpenAI = Depends(_get_llm_client),
):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        image_paths = []
        for upload in images:
            suffix = Path(upload.filename or "").suffix or ".jpg"
            dest = tmp_path / f"{uuid.uuid4().hex}{suffix}"
            with dest.open("wb") as f:
                shutil.copyfileobj(upload.file, f)
            image_paths.append(str(dest))

        form_suffix = Path(form.filename or "").suffix or ".pdf"
        form_path = tmp_path / f"{uuid.uuid4().hex}{form_suffix}"
        with form_path.open("wb") as f:
            shutil.copyfileobj(form.file, f)

        try:
            image_result = extract_from_image(image_paths, client)
            pdf_result = extract_structured_data_pdf(str(form_path), client)
            check_result = validate_results(image_result, pdf_result)
        except OpenAIError as e:
            raise HTTPException(
                status_code=502,
                detail=f"LLM service unavailable at {settings.MODAL_API_URL}. Is the server running?",
            ) from e
        except ValidationError as e:
            raise HTTPException(status_code=502, detail="LLM returned malformed output") from e

    try:
        run = VerificationRun(
            image_brand_name=image_result.brand_name,
            image_warning_label_text=image_result.warning_label_text,
            image_alcohol_content=image_result.alcohol_content,
            image_class_text=image_result.class_text,
            image_address=image_result.address,
            form_brand_name=pdf_result.brand_name,
            form_source=pdf_result.source,
            form_type=pdf_result.type,
            form_alcohol_content=pdf_result.alcohol_content,
            form_address=pdf_result.address,
            brand_match=check_result.brand_match,
            alcohol_match=check_result.alcohol_match,
            warning_match=check_result.warning_match,
        )
        session.add(run)
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail="Failed to save verification run") from e

    return check_result


@app.get("/export")
def export_csv(session: Session = Depends(get_session)):
    runs = session.exec(select(VerificationRun)).all()

    output = io.StringIO()
    fieldnames = [
        "id", "created_at",
        "image_brand_name", "image_warning_label_text", "image_alcohol_content",
        "image_class_text", "image_address",
        "form_brand_name", "form_source", "form_type", "form_alcohol_content",
        "form_address",
        "brand_match", "alcohol_match", "warning_match",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for run in runs:
        writer.writerow({field: getattr(run, field) for field in fieldnames})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=verification_runs.csv"},
    )
