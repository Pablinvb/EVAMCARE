from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from .config import REFERRAL_TOKEN_SECRET
from .database import connect


GOALS = [
    "Acne",
    "Hydration",
    "Oil control",
    "Pigmentation",
    "Anti-aging",
    "Sensitive skin",
    "General skin health",
]

METRIC_MAP = {
    "Acné": "acne_score",
    "Imperfecciones": "acne_score",
    "Hidratación": "hydration_score",
    "Pigmentación": "pigmentation_score",
    "Líneas visibles": "wrinkles_score",
    "Poros": "pores_score",
    "Enrojecimiento": "redness_score",
    "Balance sebáceo": "oiliness_score",
}


def initialize_patient_platform() -> None:
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                patient_code TEXT UNIQUE NOT NULL,
                session_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT,
                date_of_birth TEXT,
                email TEXT,
                phone TEXT,
                gender TEXT,
                city TEXT,
                country TEXT,
                skin_goals_json TEXT NOT NULL,
                demo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS skin_scans (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                scan_date TEXT NOT NULL,
                capture_source TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                acne_score INTEGER,
                hydration_score INTEGER,
                pigmentation_score INTEGER,
                wrinkles_score INTEGER,
                pores_score INTEGER,
                redness_score INTEGER,
                oiliness_score INTEGER,
                confidence_score INTEGER,
                ai_model TEXT NOT NULL,
                ai_model_version TEXT NOT NULL,
                analysis_status TEXT NOT NULL,
                analysis_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_skin_scans_patient_date "
            "ON skin_scans(patient_id, scan_date DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_images (
                id TEXT PRIMARY KEY,
                scan_id TEXT NOT NULL,
                image_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (scan_id) REFERENCES skin_scans(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                scan_id TEXT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                priority INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id),
                FOREIGN KEY (scan_id) REFERENCES skin_scans(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shared_records (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                permissions_json TEXT NOT NULL,
                recipient_type TEXT NOT NULL,
                accessed_at TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS consents (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                consent_type TEXT NOT NULL,
                granted INTEGER NOT NULL,
                granted_at TEXT,
                revoked_at TEXT,
                version TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                patient_id TEXT,
                actor_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                timestamp TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
            """
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _patient_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "DS-" + "".join(secrets.choice(alphabet) for _ in range(7))


def _audit(
    connection,
    *,
    patient_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_logs (
            id, patient_id, actor_id, action, resource_type, resource_id,
            timestamp, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            patient_id,
            actor_id,
            action,
            resource_type,
            resource_id,
            now_iso(),
            json.dumps(metadata or {}, ensure_ascii=False, separators=(",", ":")),
        ),
    )


def get_or_create_patient(session_id: str) -> dict[str, Any]:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM patients WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row:
            patient = _patient_from_row(row)
        else:
            created_at = now_iso()
            patient_id = str(uuid4())
            code = _patient_code()
            patient = {
                "id": patient_id,
                "patientCode": code,
                "firstName": "Demo",
                "lastName": "Patient",
                "email": None,
                "phone": None,
                "gender": None,
                "city": "Quito",
                "country": "Ecuador",
                "skinGoals": ["Hydration", "Acne", "General skin health"],
                "demo": True,
                "createdAt": created_at,
                "updatedAt": created_at,
            }
            connection.execute(
                """
                INSERT INTO patients (
                    id, patient_code, session_id, first_name, last_name,
                    city, country, skin_goals_json, demo, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    patient_id,
                    code,
                    session_id,
                    "Demo",
                    "Patient",
                    "Quito",
                    "Ecuador",
                    json.dumps(patient["skinGoals"], ensure_ascii=False),
                    created_at,
                    created_at,
                ),
            )
            _seed_patient_consents(connection, patient_id)
            _seed_demo_scans(connection, patient_id)
            _audit(
                connection,
                patient_id=patient_id,
                actor_id=session_id,
                action="PATIENT_CREATED",
                resource_type="patient",
                resource_id=patient_id,
                metadata={"demo": True},
            )
    return patient


def _patient_from_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "patientCode": row["patient_code"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "dateOfBirth": row["date_of_birth"],
        "email": row["email"],
        "phone": row["phone"],
        "gender": row["gender"],
        "city": row["city"],
        "country": row["country"],
        "skinGoals": json.loads(row["skin_goals_json"]),
        "demo": bool(row["demo"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _seed_patient_consents(connection, patient_id: str) -> None:
    created = now_iso()
    for consent_type in (
        "data_storage",
        "ai_analysis",
        "image_processing",
        "professional_sharing",
        "commercial_recommendations",
    ):
        connection.execute(
            """
            INSERT INTO consents (
                id, patient_id, consent_type, granted, granted_at, version
            ) VALUES (?, ?, ?, 1, ?, 'prototype-1')
            """,
            (str(uuid4()), patient_id, consent_type, created),
        )


def _seed_demo_scans(connection, patient_id: str) -> None:
    existing = connection.execute(
        "SELECT COUNT(*) AS count FROM skin_scans WHERE patient_id = ?",
        (patient_id,),
    ).fetchone()["count"]
    if existing:
        return
    base = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    demo = [
        (-45, 61, 48, 41, 58, 54, 49, 57, 45),
        (-30, 68, 58, 52, 62, 61, 57, 64, 55),
        (-16, 72, 65, 63, 67, 66, 63, 70, 62),
        (-1, 78, 72, 71, 72, 70, 69, 76, 68),
    ]
    for index, values in enumerate(demo, start=1):
        days, overall, acne, hydration, pigmentation, wrinkles, pores, redness, oil = values
        date = (base + timedelta(days=days)).isoformat()
        payload = _payload_from_scores(
            overall=overall,
            acne=acne,
            hydration=hydration,
            pigmentation=pigmentation,
            wrinkles=wrinkles,
            pores=pores,
            redness=redness,
            oiliness=oil,
            confidence=84 + index,
            skin_type="Mixta" if index < 4 else "Equilibrada",
        )
        scan_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO skin_scans (
                id, patient_id, scan_date, capture_source, overall_score,
                acne_score, hydration_score, pigmentation_score, wrinkles_score,
                pores_score, redness_score, oiliness_score, confidence_score,
                ai_model, ai_model_version, analysis_status, analysis_payload_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, 'webcam', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
            """,
            (
                scan_id,
                patient_id,
                date,
                overall,
                acne,
                hydration,
                pigmentation,
                wrinkles,
                pores,
                redness,
                oil,
                payload["confidence"],
                "DermaScan Visual Engine",
                "demo-seed",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                date,
                date,
            ),
        )
    _refresh_recommendations(connection, patient_id)


def _payload_from_scores(**scores: Any) -> dict[str, Any]:
    return {
        "overall": scores["overall"],
        "skinType": scores["skin_type"],
        "confidence": scores["confidence"],
        "metrics": [
            _metric("Imperfecciones", scores["acne"]),
            _metric("Hidratación", scores["hydration"]),
            _metric("Pigmentación", scores["pigmentation"]),
            _metric("Líneas visibles", scores["wrinkles"]),
            _metric("Poros", scores["pores"]),
            _metric("Enrojecimiento", scores["redness"]),
            _metric("Balance sebáceo", scores["oiliness"]),
        ],
        "attentionZones": [],
        "engine": {"name": "DermaScan Visual Engine", "version": "demo-seed"},
    }


def _metric(name: str, score: int) -> dict[str, Any]:
    status = "Óptimo" if score >= 80 else "Estable" if score >= 65 else "Atención"
    return {"name": name, "score": score, "status": status}


def save_patient_scan(
    session_id: str,
    result: dict[str, Any],
    *,
    capture_source: str = "webcam",
) -> tuple[str, str]:
    patient = get_or_create_patient(session_id)
    values = _normalized_values(result)
    scan_id = str(uuid4())
    created_at = now_iso()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO skin_scans (
                id, patient_id, scan_date, capture_source, overall_score,
                acne_score, hydration_score, pigmentation_score, wrinkles_score,
                pores_score, redness_score, oiliness_score, confidence_score,
                ai_model, ai_model_version, analysis_status, analysis_payload_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
            """,
            (
                scan_id,
                patient["id"],
                created_at,
                capture_source,
                values["overall_score"],
                values.get("acne_score"),
                values.get("hydration_score"),
                values.get("pigmentation_score"),
                values.get("wrinkles_score"),
                values.get("pores_score"),
                values.get("redness_score"),
                values.get("oiliness_score"),
                values.get("confidence_score"),
                "DermaScan Visual Engine",
                str(result.get("engine", {}).get("version", "0.7.0")),
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
                created_at,
                created_at,
            ),
        )
        _refresh_recommendations(connection, patient["id"], scan_id)
        _audit(
            connection,
            patient_id=patient["id"],
            actor_id=session_id,
            action="SCAN_CREATED",
            resource_type="skin_scan",
            resource_id=scan_id,
            metadata={"captureSource": capture_source, "imageStored": False},
        )
    return scan_id, created_at


def _normalized_values(result: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {
        "overall_score": int(result.get("overall", 0)),
        "confidence_score": int(result.get("confidence", 0)),
    }
    for metric in result.get("metrics", []):
        key = METRIC_MAP.get(metric.get("name"))
        if key and key not in values:
            values[key] = int(metric.get("score", 0))
    return values


def get_dashboard(session_id: str) -> dict[str, Any]:
    patient = get_or_create_patient(session_id)
    scans = list_patient_scans(session_id, 100)
    latest = scans[0] if scans else None
    return {
        "patient": patient,
        "currentSkinScore": latest["overallScore"] if latest else None,
        "lastScan": latest,
        "scanCount": len(scans),
        "metrics": latest["metrics"] if latest else [],
        "goals": patient["skinGoals"],
        "storage": {
            "provider": "sqlite",
            "imagesStored": False,
            "notice": "MVP: las imágenes no se guardan; solo se conservan resultados estructurados.",
        },
    }


def list_patient_scans(session_id: str, limit: int = 50) -> list[dict[str, Any]]:
    patient = get_or_create_patient(session_id)
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM skin_scans
            WHERE patient_id = ?
            ORDER BY scan_date DESC
            LIMIT ?
            """,
            (patient["id"], limit),
        ).fetchall()
    return [_scan_from_row(row) for row in rows]


def get_scan(session_id: str, scan_id: str) -> dict[str, Any] | None:
    patient = get_or_create_patient(session_id)
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM skin_scans WHERE id = ? AND patient_id = ?",
            (scan_id, patient["id"]),
        ).fetchone()
        if not row:
            return None
        _audit(
            connection,
            patient_id=patient["id"],
            actor_id=session_id,
            action="SCAN_VIEWED",
            resource_type="skin_scan",
            resource_id=scan_id,
        )
    return _scan_from_row(row)


def _scan_from_row(row) -> dict[str, Any]:
    payload = json.loads(row["analysis_payload_json"])
    return {
        "id": row["id"],
        "patientId": row["patient_id"],
        "scanDate": row["scan_date"],
        "captureSource": row["capture_source"],
        "overallScore": row["overall_score"],
        "confidenceScore": row["confidence_score"],
        "aiModel": row["ai_model"],
        "aiModelVersion": row["ai_model_version"],
        "analysisStatus": row["analysis_status"],
        "metrics": [
            {"key": "acne", "label": "Acné / imperfecciones", "score": row["acne_score"]},
            {"key": "hydration", "label": "Hidratación", "score": row["hydration_score"]},
            {"key": "oiliness", "label": "Balance sebáceo", "score": row["oiliness_score"]},
            {"key": "pores", "label": "Poros", "score": row["pores_score"]},
            {"key": "pigmentation", "label": "Pigmentación", "score": row["pigmentation_score"]},
            {"key": "wrinkles", "label": "Líneas visibles", "score": row["wrinkles_score"]},
            {"key": "redness", "label": "Enrojecimiento", "score": row["redness_score"]},
        ],
        "analysisPayload": payload,
        "imageStored": False,
    }


def get_timeline(session_id: str) -> dict[str, Any]:
    scans = list(reversed(list_patient_scans(session_id, 100)))
    if not scans:
        return {"items": [], "changes": []}
    first = scans[0]
    current = scans[-1]
    changes = []
    for index, metric in enumerate(current["metrics"]):
        initial_score = first["metrics"][index]["score"]
        current_score = metric["score"]
        if initial_score is None or current_score is None:
            continue
        changes.append(
            {
                "key": metric["key"],
                "label": metric["label"],
                "initial": initial_score,
                "current": current_score,
                "change": current_score - initial_score,
            }
        )
    return {
        "items": scans,
        "changes": changes,
        "language": "Observed change; no se infiere causalidad médica.",
    }


def compare_scans(session_id: str, scan_a: str, scan_b: str) -> dict[str, Any] | None:
    first = get_scan(session_id, scan_a)
    second = get_scan(session_id, scan_b)
    if not first or not second:
        return None
    rows = []
    for index, metric in enumerate(second["metrics"]):
        initial_score = first["metrics"][index]["score"]
        current_score = metric["score"]
        rows.append(
            {
                "key": metric["key"],
                "label": metric["label"],
                "initial": initial_score,
                "current": current_score,
                "change": None
                if initial_score is None or current_score is None
                else current_score - initial_score,
            }
        )
    return {"scanA": first, "scanB": second, "metrics": rows}


def list_recommendations(session_id: str) -> list[dict[str, Any]]:
    patient = get_or_create_patient(session_id)
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM recommendations
            WHERE patient_id = ?
            ORDER BY priority, created_at DESC
            """,
            (patient["id"],),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "scanId": row["scan_id"],
            "category": row["category"],
            "title": row["title"],
            "description": row["description"],
            "priority": row["priority"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def _refresh_recommendations(connection, patient_id: str, scan_id: str | None = None) -> None:
    latest = connection.execute(
        """
        SELECT * FROM skin_scans
        WHERE patient_id = ?
        ORDER BY scan_date DESC
        LIMIT 1
        """,
        (patient_id,),
    ).fetchone()
    if not latest:
        return
    connection.execute("DELETE FROM recommendations WHERE patient_id = ?", (patient_id,))
    candidates = [
        ("hydration", "Refuerzo de hidratación", latest["hydration_score"], "Considera una rutina con limpiador suave, humectante con ceramidas o ácido hialurónico y SPF diario."),
        ("acne", "Control cosmético de imperfecciones", latest["acne_score"], "Tu análisis sugiere vigilar brotes visibles. Usa productos no comedogénicos y evita exfoliación agresiva."),
        ("pores", "Textura y poros", latest["pores_score"], "Una rutina constante con limpieza suave y niacinamida puede ser potencialmente adecuada."),
        ("pigmentation", "Tono y pigmentación", latest["pigmentation_score"], "Prioriza fotoprotección. Si aparecen manchas nuevas o cambiantes, considera consulta profesional."),
        ("anti-aging", "Líneas visibles", latest["wrinkles_score"], "Mantén hidratación, protección solar y activos cosméticos de tolerancia progresiva."),
        ("redness", "Confort y sensibilidad", latest["redness_score"], "Elige fórmulas simples y suspende productos que generen ardor o irritación persistente."),
    ]
    rows = []
    priority = 1
    for category, title, score, description in sorted(
        candidates, key=lambda item: 101 if item[2] is None else item[2]
    )[:4]:
        rows.append(
            (
                str(uuid4()),
                patient_id,
                scan_id or latest["id"],
                category,
                title,
                description,
                priority,
                now_iso(),
            )
        )
        priority += 1
    connection.executemany(
        """
        INSERT INTO recommendations (
            id, patient_id, scan_id, category, title, description, priority, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def create_share_session(
    session_id: str,
    *,
    permissions: list[str],
    recipient_type: str,
    expires_in_hours: int,
) -> dict[str, Any]:
    patient = get_or_create_patient(session_id)
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    created_at = now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)).isoformat()
    share_id = str(uuid4())
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO shared_records (
                id, patient_id, token_hash, created_at, expires_at,
                permissions_json, recipient_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                share_id,
                patient["id"],
                token_hash,
                created_at,
                expires_at,
                json.dumps(permissions, ensure_ascii=False),
                recipient_type,
            ),
        )
        _audit(
            connection,
            patient_id=patient["id"],
            actor_id=session_id,
            action="RECORD_SHARED",
            resource_type="shared_record",
            resource_id=share_id,
            metadata={"permissions": permissions, "recipientType": recipient_type},
        )
    return {
        "id": share_id,
        "token": token,
        "createdAt": created_at,
        "expiresAt": expires_at,
        "permissions": permissions,
        "recipientType": recipient_type,
        "revokedAt": None,
    }


def revoke_share_session(session_id: str, share_id: str) -> bool:
    patient = get_or_create_patient(session_id)
    revoked_at = now_iso()
    with connect() as connection:
        cursor = connection.execute(
            """
            UPDATE shared_records SET revoked_at = ?
            WHERE id = ? AND patient_id = ? AND revoked_at IS NULL
            """,
            (revoked_at, share_id, patient["id"]),
        )
        if cursor.rowcount:
            _audit(
                connection,
                patient_id=patient["id"],
                actor_id=session_id,
                action="SHARE_REVOKED",
                resource_type="shared_record",
                resource_id=share_id,
            )
    return cursor.rowcount > 0


def list_share_sessions(session_id: str) -> list[dict[str, Any]]:
    patient = get_or_create_patient(session_id)
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, expires_at, revoked_at, permissions_json,
                   recipient_type, accessed_at
            FROM shared_records
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (patient["id"],),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "expiresAt": row["expires_at"],
            "revokedAt": row["revoked_at"],
            "permissions": json.loads(row["permissions_json"]),
            "recipientType": row["recipient_type"],
            "accessedAt": row["accessed_at"],
        }
        for row in rows
    ]


def _hash_token(token: str) -> str:
    return hmac.new(
        REFERRAL_TOKEN_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

