from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Annotated

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .analyzer import SkinAnalyzer
from .config import (
    ALLOWED_CONTENT_TYPES,
    APP_NAME,
    APP_VERSION,
    MAX_IMAGE_PIXELS,
    MAX_UPLOAD_BYTES,
    PROJECT_ROOT,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
)
from .clinical_status import get_clinical_status
from .database import (
    delete_analysis,
    delete_session_history,
    initialize_database,
    list_analyses,
    save_analysis,
)

SESSION_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{16,80}$")
rate_buckets: dict[str, deque[float]] = defaultdict(deque)
rate_lock = threading.Lock()
analyzer = SkinAnalyzer()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API experimental para evaluación cosmética de señales visibles. "
        "No es un dispositivo médico ni emite diagnósticos."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:4187",
        "http://localhost:4187",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Derma-Session"],
)


def validate_session(session_id: str | None) -> str:
    if not session_id or not SESSION_PATTERN.fullmatch(session_id):
        raise HTTPException(status_code=400, detail="Identificador de sesión inválido.")
    return session_id


def enforce_rate_limit(session_id: str) -> None:
    now = time.monotonic()
    with rate_lock:
        bucket = rate_buckets[session_id]
        while bucket and now - bucket[0] > RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Límite temporal de análisis alcanzado. Intenta más tarde.",
            )
        bucket.append(now)


async def decode_upload(image: UploadFile) -> np.ndarray:
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Formato no permitido. Usa JPEG, PNG o WebP.",
        )
    contents = await image.read(MAX_UPLOAD_BYTES + 1)
    await image.close()
    if not contents:
        raise HTTPException(status_code=400, detail="La imagen está vacía.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="La imagen supera el límite de 10 MB.")
    array = np.frombuffer(contents, dtype=np.uint8)
    decoded = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=422, detail="No se pudo decodificar la imagen.")
    height, width = decoded.shape[:2]
    if height < 240 or width < 240:
        raise HTTPException(
            status_code=422,
            detail="La imagen debe medir al menos 240 × 240 píxeles.",
        )
    if height * width > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="La resolución supera el límite de 16 megapíxeles.",
        )
    return decoded


@app.exception_handler(HTTPException)
async def http_error_handler(_, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": {
                "code": 422,
                "message": "La solicitud no contiene todos los datos requeridos.",
                "details": exc.errors(),
            },
        },
    )


@app.get("/api/v1/health")
def health() -> dict:
    return {
        "ok": True,
        "service": APP_NAME,
        "version": APP_VERSION,
        "analyzer": "ready",
        "storesImages": False,
        "clinicalStatus": "research_only",
    }


@app.get("/api/v1/clinical-status")
def clinical_status() -> dict:
    return {"ok": True, **get_clinical_status()}


@app.post("/api/v1/analyze")
async def analyze(
    image: Annotated[UploadFile, File(description="Fotografía facial JPEG, PNG o WebP")],
    save_history: Annotated[bool, Form()] = False,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    enforce_rate_limit(session_id)
    decoded = await decode_upload(image)
    result = await run_in_threadpool(analyzer.analyze, decoded)
    analysis_id = None
    created_at = None
    if save_history:
        analysis_id, created_at = save_analysis(session_id, result)
    return {
        "ok": True,
        "analysisId": analysis_id,
        "createdAt": created_at,
        "stored": bool(save_history),
        "imageStored": False,
        "result": result,
        "disclaimer": (
            "Evaluación cosmética experimental. No detecta enfermedades ni "
            "sustituye una consulta dermatológica."
        ),
    }


@app.get("/api/v1/history")
def history(
    x_derma_session: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "items": list_analyses(session_id, limit)}


@app.delete("/api/v1/history/{analysis_id}")
def remove_analysis(
    analysis_id: str,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    if not delete_analysis(session_id, analysis_id):
        raise HTTPException(status_code=404, detail="Análisis no encontrado.")
    return {"ok": True, "deleted": analysis_id}


@app.delete("/api/v1/history")
def clear_history(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "deleted": delete_session_history(session_id)}


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/index.html", include_in_schema=False)
def frontend_index_alias() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/styles.css", include_in_schema=False)
def frontend_styles() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def frontend_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app.js", media_type="text/javascript")
