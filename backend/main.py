from __future__ import annotations

import re
import threading
import time
from math import asin, cos, radians, sin, sqrt
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Literal

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .analyzer import SkinAnalyzer
from .accounts import router as accounts_router, initialize_accounts, current_user, record_session
from .config import (
    ALLOWED_CONTENT_TYPES,
    APP_NAME,
    APP_VERSION,
    CORS_ORIGINS,
    ENVIRONMENT,
    MAX_IMAGE_PIXELS,
    MAX_UPLOAD_BYTES,
    PROJECT_ROOT,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    PARTNER_API_KEY,
    REFERRAL_TOKEN_TTL_SECONDS,
)
from .clinical_status import get_clinical_status
from .guidance import evaluate_guidance, recommend_products
from .database import (
    create_appointment,
    delete_analysis,
    delete_lead,
    delete_session_history,
    get_active_clinics,
    get_active_stores,
    get_available_slots,
    get_clinic,
    get_store,
    get_store_products,
    initialize_database,
    create_partner_slots,
    list_partner_appointments,
    list_partner_leads,
    list_guidance_assessments,
    list_analyses,
    save_analysis,
    save_guidance_assessment,
    save_lead,
    update_partner_appointment,
    upsert_partner_clinic,
)
from .referrals import create_referral_token, verify_referral_token
from .patient_platform import (
    compare_scans,
    create_share_session,
    get_dashboard,
    get_or_create_patient,
    get_scan,
    get_timeline,
    initialize_patient_platform,
    list_patient_scans,
    list_recommendations,
    list_share_sessions,
    revoke_share_session,
    save_patient_scan,
)

SESSION_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{16,80}$")
rate_buckets: dict[str, deque[float]] = defaultdict(deque)
rate_lock = threading.Lock()
analyzer = SkinAnalyzer()


class LeadRequest(BaseModel):
    clinicId: str = Field(min_length=3, max_length=80)
    referralToken: str = Field(min_length=20, max_length=5000)
    fullName: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=7, max_length=30)
    email: str | None = Field(default=None, max_length=254)
    preferredChannel: str = Field(pattern="^(phone|whatsapp|email)$")
    preferredTime: str | None = Field(default=None, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distanceKm: float = Field(ge=0, le=500)
    consentContact: bool
    consentLocation: bool
    consentResults: bool


class GuidanceAnswers(BaseModel):
    rapidlyWorsening: bool = False
    feverOrUnwell: bool = False
    eyesMouthBlisters: bool = False
    changingBleedingSpot: bool = False
    notHealing: bool = False
    marksChangingOrUnexplained: bool = False
    persistentConcern: bool = False
    itchSeverity: Literal["none", "mild", "intense_persistent"] = "none"
    duration: Literal["under_2_weeks", "2_to_6_weeks", "over_6_weeks"] = "under_2_weeks"
    painLevel: Literal["none", "mild", "moderate_severe"] = "none"
    inflammation: bool = False
    discharge: bool = False
    personalSkinCancer: bool = False
    familyMelanoma: bool = False
    immunosuppressed: bool = False


class GuidanceRequest(BaseModel):
    referralToken: str = Field(min_length=20, max_length=5000)
    answers: GuidanceAnswers
    saveHistory: bool = False


class AppointmentRequest(LeadRequest):
    slotId: str = Field(min_length=5, max_length=120)


class PartnerClinicRequest(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=3, max_length=160)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5, max_length=240)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    services: list[str] = Field(min_length=1, max_length=12)


class PartnerSlotsRequest(BaseModel):
    startsAt: list[datetime] = Field(min_length=1, max_length=60)


class PartnerAppointmentStatusRequest(BaseModel):
    status: Literal["confirmed", "completed", "cancelled", "no-show"]


class ShareRecordRequest(BaseModel):
    permissions: list[
        Literal["profile", "scans", "images", "evolution", "recommendations"]
    ] = Field(default_factory=lambda: ["profile", "scans", "evolution"])
    recipientType: Literal[
        "dermatologist", "cosmetologist", "clinic", "skincare_provider", "other"
    ] = "dermatologist"
    expiresInHours: int = Field(default=72, ge=1, le=720)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    initialize_patient_platform()
    initialize_accounts()
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
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Derma-Session", "X-Partner-Key", "Authorization", "X-Patient-ID"],
)
app.include_router(accounts_router)

@app.middleware("http")
async def account_patient_context(request, call_next):
    path = request.url.path
    protected = path.startswith("/api/v1/patients/me") or path == "/api/v1/analyze" or path.startswith("/api/v1/shares/")
    if protected and request.headers.get("authorization"):
        try:
            user = current_user(request.headers.get("authorization"))
            pid = request.headers.get("x-patient-id") or user['patient_id']
            if not pid:
                raise HTTPException(400, "Selecciona un paciente autorizado")
            session = record_session(user, pid)
            headers = [(k,v) for k,v in request.scope['headers'] if k.lower()!=b'x-derma-session']
            headers.append((b'x-derma-session',session.encode()))
            request.scope['headers'] = headers
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code,content={'detail':exc.detail})
    return await call_next(request)


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
        "environment": ENVIRONMENT,
    }


@app.get("/api/v1/clinical-status")
def clinical_status() -> dict:
    return {"ok": True, **get_clinical_status()}


@app.post("/api/v1/analyze")
async def analyze(
    image: Annotated[UploadFile, File(description="Fotografía facial JPEG, PNG o WebP")],
    save_history: Annotated[bool, Form()] = False,
    patient_consent: Annotated[bool, Form()] = False,
    capture_source: Annotated[
        Literal["webcam", "iphone", "upload", "vision_pro"], Form()
    ] = "webcam",
    x_derma_session: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if authorization and not patient_consent:
        raise HTTPException(400, "Confirma el consentimiento del paciente antes de evaluar")
    session_id = validate_session(x_derma_session)
    enforce_rate_limit(session_id)
    decoded = await decode_upload(image)
    result = await run_in_threadpool(analyzer.analyze, decoded)
    referral_token = create_referral_token(result)
    analysis_id = None
    patient_scan_id = None
    created_at = None
    if save_history:
        analysis_id, created_at = save_analysis(session_id, result)
        patient_scan_id, created_at = save_patient_scan(
            session_id,
            result,
            capture_source=capture_source,
        )
    return {
        "ok": True,
        "analysisId": analysis_id,
        "patientScanId": patient_scan_id,
        "createdAt": created_at,
        "stored": bool(save_history),
        "imageStored": False,
        "referralToken": referral_token,
        "referralTokenExpiresIn": REFERRAL_TOKEN_TTL_SECONDS,
        "result": result,
        "disclaimer": (
            "Evaluación cosmética experimental. No detecta enfermedades ni "
            "sustituye una consulta dermatológica."
        ),
    }


@app.get("/api/v1/patients/me")
def patient_profile(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "patient": get_or_create_patient(session_id)}


@app.get("/api/v1/patients/me/dashboard")
def patient_dashboard(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, **get_dashboard(session_id)}


@app.get("/api/v1/patients/me/scans")
def patient_scans(
    x_derma_session: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "items": list_patient_scans(session_id, limit)}


@app.get("/api/v1/patients/me/scans/{scan_id}")
def patient_scan_detail(
    scan_id: str,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    scan = get_scan(session_id, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Escaneo no encontrado.")
    return {"ok": True, "scan": scan}


@app.get("/api/v1/patients/me/timeline")
def patient_timeline(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, **get_timeline(session_id)}


@app.get("/api/v1/patients/me/compare")
def patient_scan_comparison(
    scan_a: Annotated[str, Query(min_length=10)],
    scan_b: Annotated[str, Query(min_length=10)],
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    comparison = compare_scans(session_id, scan_a, scan_b)
    if not comparison:
        raise HTTPException(status_code=404, detail="No se pudieron comparar los escaneos.")
    return {"ok": True, **comparison}


@app.get("/api/v1/patients/me/recommendations")
def patient_recommendations(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {
        "ok": True,
        "items": list_recommendations(session_id),
        "disclaimer": (
            "Recomendaciones cosméticas orientativas. No son diagnóstico ni tratamiento médico."
        ),
    }


@app.get("/api/v1/patients/me/shares")
def patient_shares(
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "items": list_share_sessions(session_id)}


@app.post("/api/v1/patients/me/share", status_code=201)
def create_patient_share(
    request: ShareRecordRequest,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    if not request.permissions:
        raise HTTPException(status_code=400, detail="Selecciona al menos un permiso.")
    share = create_share_session(
        session_id,
        permissions=list(dict.fromkeys(request.permissions)),
        recipient_type=request.recipientType,
        expires_in_hours=request.expiresInHours,
    )
    return {
        "ok": True,
        "share": share,
        "notice": (
            "Token creado para demo. En producción debe entregarse por canal seguro "
            "y validarse con autenticación profesional."
        ),
    }


@app.post("/api/v1/shares/{share_id}/revoke")
def revoke_patient_share(
    share_id: str,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    if not revoke_share_session(session_id, share_id):
        raise HTTPException(status_code=404, detail="Share no encontrado o ya revocado.")
    return {"ok": True, "shareId": share_id, "revoked": True}


@app.get("/api/v1/capture-providers")
def capture_providers() -> dict:
    return {
        "ok": True,
        "items": [
            {
                "id": "standard-camera",
                "captureSource": "webcam",
                "name": "Standard Scan",
                "status": "available",
                "description": "Reutiliza el scanner facial web actual.",
            },
            {
                "id": "upload",
                "captureSource": "upload",
                "name": "Upload Scan",
                "status": "available",
                "description": "Permite analizar fotografías subidas por el usuario.",
            },
            {
                "id": "vision-pro",
                "captureSource": "vision_pro",
                "name": "Spatial Scan / Vision Pro Ready",
                "status": "demo_adapter",
                "description": (
                    "Arquitectura preparada para captura espacial. No indica hardware Vision Pro conectado."
                ),
            },
        ],
    }


def distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    earth_radius = 6371.0088
    lat_a, lat_b = radians(latitude_a), radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = radians(longitude_b - longitude_a)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    )
    return earth_radius * 2 * asin(sqrt(value))


@app.get("/api/v1/clinics")
def clinics(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(ge=1, le=200)] = 50,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict:
    matches = []
    for clinic in get_active_clinics():
        distance = distance_km(
            latitude, longitude, clinic["latitude"], clinic["longitude"]
        )
        if distance <= radius_km:
            public_clinic = {
                key: value
                for key, value in clinic.items()
                if key not in {"latitude", "longitude"}
            }
            public_clinic["distanceKm"] = round(distance, 1)
            matches.append(public_clinic)
    matches.sort(key=lambda item: item["distanceKm"])
    return {
        "ok": True,
        "items": matches[:limit],
        "locationStored": False,
        "notice": (
            "Los centros marcados como demo son datos demostrativos y no representan "
            "alianzas comerciales verificadas."
        ),
    }


@app.post("/api/v1/guidance")
def guidance(
    request: GuidanceRequest,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    try:
        summary = verify_referral_token(request.referralToken)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = evaluate_guidance(summary, request.answers.model_dump())
    assessment_id = None
    created_at = None
    if request.saveHistory:
        session_id = validate_session(x_derma_session)
        assessment_id, created_at = save_guidance_assessment(
            session_id,
            request.answers.model_dump(),
            result,
        )
    return {
        "ok": True,
        "guidance": result,
        "stored": request.saveHistory,
        "assessmentId": assessment_id,
        "createdAt": created_at,
    }


@app.get("/api/v1/guidance-history")
def guidance_history(
    x_derma_session: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    session_id = validate_session(x_derma_session)
    return {"ok": True, "items": list_guidance_assessments(session_id, limit)}


@app.get("/api/v1/stores")
def stores(
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(ge=1, le=200)] = 50,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> dict:
    matches = []
    for store in get_active_stores():
        if store.get("online"):
            public_store = {
                key: value
                for key, value in store.items()
                if key not in {"latitude", "longitude"}
            }
            public_store["distanceKm"] = None
            matches.append(public_store)
            continue
        distance = distance_km(
            latitude, longitude, store["latitude"], store["longitude"]
        )
        if distance <= radius_km:
            public_store = {
                key: value
                for key, value in store.items()
                if key not in {"latitude", "longitude"}
            }
            public_store["distanceKm"] = round(distance, 1)
            matches.append(public_store)
    matches.sort(
        key=lambda item: (
            not item.get("online", False),
            item["distanceKm"] if item["distanceKm"] is not None else 0,
        )
    )
    return {
        "ok": True,
        "items": matches[:limit],
        "locationStored": False,
        "notice": "Las tiendas demo no representan convenios ni disponibilidad comercial real.",
    }


@app.get("/api/v1/stores/{store_id}/recommendations")
def store_recommendations(
    store_id: str,
    referral_token: Annotated[str, Query(min_length=20, max_length=5000)],
) -> dict:
    store = get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Tienda no encontrada.")
    try:
        summary = verify_referral_token(referral_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    products = recommend_products(summary, get_store_products(store_id))
    return {
        "ok": True,
        "store": {
            key: value for key, value in store.items() if key not in {"latitude", "longitude"}
        },
        "products": products,
        "routine": _build_routine(products, summary.get("skinType", "Equilibrada")),
        "disclaimer": (
            "Sugerencias cosméticas orientativas. Suspende el uso si aparece irritación "
            "y consulta a un profesional ante síntomas persistentes o de alerta."
        ),
    }


def _build_routine(products: list[dict], skin_type: str) -> dict:
    steps = []
    labels = {
        "cleanse": ("Limpieza", "Mañana y noche"),
        "treat": ("Tratamiento", "Una vez al día según tolerancia"),
        "moisturize": ("Hidratación", "Mañana y noche"),
        "protect": ("Protección solar", "Cada mañana y reaplicar"),
    }
    for step in ("cleanse", "treat", "moisturize", "protect"):
        product = next(
            (item for item in products if item.get("routineStep") == step),
            None,
        )
        if product:
            steps.append(
                {
                    "step": step,
                    "title": labels[step][0],
                    "frequency": labels[step][1],
                    "productId": product["id"],
                }
            )
    return {
        "skinType": skin_type,
        "morningOrder": ["cleanse", "treat", "moisturize", "protect"],
        "nightOrder": ["cleanse", "treat", "moisturize"],
        "steps": steps,
    }


@app.get("/api/v1/clinics/{clinic_id}/availability")
def clinic_availability(clinic_id: str) -> dict:
    clinic = get_clinic(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Centro no encontrado.")
    return {"ok": True, "items": get_available_slots(clinic_id)}


@app.post("/api/v1/appointments", status_code=201)
def book_appointment(
    request: AppointmentRequest,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    lead_response = create_lead(request, x_derma_session)
    session_id = validate_session(x_derma_session)
    try:
        appointment_id, created_at, starts_at = create_appointment(
            lead_id=lead_response["leadId"],
            slot_id=request.slotId,
            clinic_id=request.clinicId,
            session_id=session_id,
        )
    except ValueError as exc:
        delete_lead(session_id, lead_response["leadId"])
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "ok": True,
        "appointmentId": appointment_id,
        "leadId": lead_response["leadId"],
        "createdAt": created_at,
        "startsAt": starts_at,
        "status": "requested",
        "clinic": lead_response["clinic"],
        "imageShared": False,
        "message": (
            "La solicitud de cita fue registrada. El centro debe confirmarla."
        ),
    }


@app.post("/api/v1/leads", status_code=201)
def create_lead(
    request: LeadRequest,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    enforce_rate_limit(session_id)
    if not (
        request.consentContact
        and request.consentLocation
        and request.consentResults
    ):
        raise HTTPException(
            status_code=400,
            detail="Se requieren los tres consentimientos para enviar la solicitud.",
        )
    clinic = get_clinic(request.clinicId)
    if not clinic:
        raise HTTPException(status_code=404, detail="Centro no encontrado.")
    calculated_distance = distance_km(
        request.latitude,
        request.longitude,
        clinic["latitude"],
        clinic["longitude"],
    )
    if abs(calculated_distance - request.distanceKm) > 3:
        raise HTTPException(
            status_code=400,
            detail="La distancia del centro no coincide con la ubicación enviada.",
        )
    try:
        summary = verify_referral_token(request.referralToken)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if request.email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", request.email):
        raise HTTPException(status_code=400, detail="Correo electrónico inválido.")
    rounded_latitude = round(request.latitude, 3)
    rounded_longitude = round(request.longitude, 3)
    consent_text = (
        "El usuario autorizó compartir contacto, ubicación aproximada y resumen "
        "del análisis con el centro seleccionado. La fotografía no fue compartida."
    )
    lead_id, created_at = save_lead(
        clinic_id=request.clinicId,
        session_id=session_id,
        full_name=request.fullName.strip(),
        phone=request.phone.strip(),
        email=request.email.strip() if request.email else None,
        preferred_channel=request.preferredChannel,
        preferred_time=request.preferredTime.strip() if request.preferredTime else None,
        latitude=rounded_latitude,
        longitude=rounded_longitude,
        distance_km=round(calculated_distance, 1),
        analysis_summary=summary,
        consent_text=consent_text,
    )
    return {
        "ok": True,
        "leadId": lead_id,
        "createdAt": created_at,
        "status": "new",
        "clinic": {"id": clinic["id"], "name": clinic["name"]},
        "imageShared": False,
        "message": "Tu solicitud fue registrada para que el centro pueda contactarte.",
    }


@app.delete("/api/v1/leads/{lead_id}")
def remove_lead(
    lead_id: str,
    x_derma_session: Annotated[str | None, Header()] = None,
) -> dict:
    session_id = validate_session(x_derma_session)
    if not delete_lead(session_id, lead_id):
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    return {"ok": True, "deleted": lead_id}


@app.get("/api/v1/partner/leads")
def partner_leads(
    clinic_id: Annotated[str, Query(min_length=3, max_length=80)],
    x_partner_key: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    if not x_partner_key or not hmac_compare(x_partner_key, PARTNER_API_KEY):
        raise HTTPException(status_code=401, detail="Credencial de socio inválida.")
    if not get_clinic(clinic_id):
        raise HTTPException(status_code=404, detail="Centro no encontrado.")
    return {"ok": True, "items": list_partner_leads(clinic_id, limit)}


def hmac_compare(value_a: str, value_b: str) -> bool:
    import hmac

    return hmac.compare_digest(value_a.encode("utf-8"), value_b.encode("utf-8"))


def require_partner_key(value: str | None) -> None:
    if not value or not hmac_compare(value, PARTNER_API_KEY):
        raise HTTPException(status_code=401, detail="Credencial de socio inválida.")


@app.put("/api/v1/partner/clinics")
def save_partner_clinic(
    request: PartnerClinicRequest,
    x_partner_key: Annotated[str | None, Header()] = None,
) -> dict:
    require_partner_key(x_partner_key)
    clinic = request.model_dump()
    clinic["services"] = [
        service.strip() for service in clinic["services"] if service.strip()
    ]
    if not clinic["services"]:
        raise HTTPException(status_code=400, detail="Incluye al menos un servicio.")
    upsert_partner_clinic(clinic)
    return {"ok": True, "clinic": get_clinic(request.id)}


@app.post("/api/v1/partner/clinics/{clinic_id}/availability", status_code=201)
def add_partner_availability(
    clinic_id: str,
    request: PartnerSlotsRequest,
    x_partner_key: Annotated[str | None, Header()] = None,
) -> dict:
    require_partner_key(x_partner_key)
    clinic = get_clinic(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Centro no encontrado.")
    now = datetime.now(timezone.utc)
    starts_at_values: list[str] = []
    for value in request.startsAt:
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        normalized = normalized.astimezone(timezone.utc)
        if normalized <= now:
            raise HTTPException(
                status_code=400,
                detail="Todos los horarios deben estar en el futuro.",
            )
        starts_at_values.append(normalized.isoformat())
    return {
        "ok": True,
        "clinicId": clinic_id,
        "items": create_partner_slots(clinic_id, starts_at_values),
    }


@app.get("/api/v1/partner/appointments")
def partner_appointments(
    clinic_id: Annotated[str, Query(min_length=3, max_length=80)],
    x_partner_key: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    require_partner_key(x_partner_key)
    if not get_clinic(clinic_id):
        raise HTTPException(status_code=404, detail="Centro no encontrado.")
    return {"ok": True, "items": list_partner_appointments(clinic_id, limit)}


@app.patch("/api/v1/partner/appointments/{appointment_id}")
def change_partner_appointment_status(
    appointment_id: str,
    request: PartnerAppointmentStatusRequest,
    clinic_id: Annotated[str, Query(min_length=3, max_length=80)],
    x_partner_key: Annotated[str | None, Header()] = None,
) -> dict:
    require_partner_key(x_partner_key)
    if not update_partner_appointment(clinic_id, appointment_id, request.status):
        raise HTTPException(status_code=404, detail="Cita no encontrada.")
    return {
        "ok": True,
        "appointmentId": appointment_id,
        "status": request.status,
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


@app.get("/config.js", include_in_schema=False)
def frontend_config() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "config.js", media_type="text/javascript")


@app.get("/assets/{asset_name}", include_in_schema=False)
def frontend_asset(asset_name: str) -> FileResponse:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", asset_name):
        raise HTTPException(status_code=404, detail="Asset no encontrado.")
    path = PROJECT_ROOT / "assets" / asset_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset no encontrado.")
    media_type = "image/png" if asset_name.endswith(".png") else None
    return FileResponse(path, media_type=media_type)
