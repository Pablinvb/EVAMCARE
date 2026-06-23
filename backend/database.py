import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from .config import DATABASE_PATH, DATA_DIR
from .catalog_data import PRODUCTS as REAL_PRODUCTS
from .catalog_data import RETAILERS, VERIFIED_AT


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                overall_score INTEGER NOT NULL,
                skin_type TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                result_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_session_created "
            "ON analyses(session_id, created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS clinics (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                phone TEXT,
                whatsapp TEXT,
                services_json TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                demo INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                clinic_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                full_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                preferred_channel TEXT NOT NULL,
                preferred_time TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                distance_km REAL NOT NULL,
                analysis_summary_json TEXT NOT NULL,
                consent_contact INTEGER NOT NULL,
                consent_location INTEGER NOT NULL,
                consent_results INTEGER NOT NULL,
                consent_text TEXT NOT NULL,
                FOREIGN KEY (clinic_id) REFERENCES clinics(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_clinic_created "
            "ON leads(clinic_id, created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stores (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                address TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
                demo INTEGER NOT NULL DEFAULT 1,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                ingredients_json TEXT NOT NULL,
                concerns_json TEXT NOT NULL,
                usage_text TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                stock INTEGER NOT NULL DEFAULT 1,
                demo INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (store_id) REFERENCES stores(id)
            )
            """
        )
        _ensure_column(connection, "stores", "website", "TEXT")
        _ensure_column(connection, "stores", "online", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "stores", "retailer_code", "TEXT")
        _ensure_column(connection, "products", "brand", "TEXT")
        _ensure_column(connection, "products", "source_url", "TEXT")
        _ensure_column(connection, "products", "skin_types_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_column(connection, "products", "routine_step", "TEXT")
        _ensure_column(connection, "products", "verified_at", "TEXT")
        _ensure_column(connection, "products", "external_reference", "INTEGER NOT NULL DEFAULT 0")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS appointment_slots (
                id TEXT PRIMARY KEY,
                clinic_id TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                available INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (clinic_id) REFERENCES clinics(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                slot_id TEXT NOT NULL UNIQUE,
                clinic_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'requested',
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (slot_id) REFERENCES appointment_slots(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS guidance_assessments (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_score REAL NOT NULL,
                route TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                consent_history INTEGER NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_guidance_session_created "
            "ON guidance_assessments(session_id, created_at DESC)"
        )
        _seed_demo_clinics(connection)
        _seed_demo_stores(connection)
        _seed_real_retailers(connection)
        _ensure_demo_slots(connection)


def _ensure_column(
    connection: sqlite3.Connection, table: str, column: str, declaration: str
) -> None:
    columns = {
        row["name"] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def save_analysis(session_id: str, result: dict[str, Any]) -> tuple[str, str]:
    analysis_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO analyses
                (id, session_id, created_at, overall_score, skin_type, confidence, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                session_id,
                created_at,
                result["overall"],
                result["skinType"],
                result["confidence"],
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    return analysis_id, created_at


def list_analyses(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, overall_score, skin_type, confidence, result_json
            FROM analyses
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "overall": row["overall_score"],
            "skinType": row["skin_type"],
            "confidence": row["confidence"],
            "result": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def delete_analysis(session_id: str, analysis_id: str) -> bool:
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM analyses WHERE id = ? AND session_id = ?",
            (analysis_id, session_id),
        )
    return cursor.rowcount > 0


def delete_session_history(session_id: str) -> int:
    with connect() as connection:
        guidance_deleted = connection.execute(
            "DELETE FROM guidance_assessments WHERE session_id = ?",
            (session_id,),
        ).rowcount
        cursor = connection.execute(
            "DELETE FROM analyses WHERE session_id = ?",
            (session_id,),
        )
    return cursor.rowcount + guidance_deleted


def save_guidance_assessment(
    session_id: str,
    answers: dict[str, Any],
    result: dict[str, Any],
) -> tuple[str, str]:
    assessment_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO guidance_assessments (
                id, session_id, created_at, risk_level, risk_score, route,
                answers_json, result_json, consent_history
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                assessment_id,
                session_id,
                created_at,
                result["riskLevel"],
                result["riskScore"],
                result["route"],
                json.dumps(answers, ensure_ascii=False, separators=(",", ":")),
                json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            ),
        )
    return assessment_id, created_at


def list_guidance_assessments(
    session_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, risk_level, risk_score, route,
                   answers_json, result_json
            FROM guidance_assessments
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "riskLevel": row["risk_level"],
            "riskScore": row["risk_score"],
            "route": row["route"],
            "answers": json.loads(row["answers_json"]),
            "result": json.loads(row["result_json"]),
        }
        for row in rows
    ]


def _seed_demo_clinics(connection: sqlite3.Connection) -> None:
    clinics = [
        (
            "demo-quito-norte",
            "Centro Dermatológico Norte · Demo",
            "Quito",
            "Sector Iñaquito · ubicación demostrativa",
            -0.1767,
            -78.4800,
            "+593 2 000 0001",
            "+593 99 000 0001",
            ["Dermatología general", "Acné", "Seguimiento de piel"],
        ),
        (
            "demo-quito-centro",
            "Clínica de Piel Centro · Demo",
            "Quito",
            "Sector Centro Norte · ubicación demostrativa",
            -0.2030,
            -78.4935,
            "+593 2 000 0002",
            "+593 99 000 0002",
            ["Dermatología", "Pigmentación", "Consulta preventiva"],
        ),
        (
            "demo-cumbaya",
            "Instituto Dermatológico Cumbayá · Demo",
            "Quito",
            "Sector Cumbayá · ubicación demostrativa",
            -0.2006,
            -78.4287,
            "+593 2 000 0003",
            "+593 99 000 0003",
            ["Dermatología general", "Textura", "Cuidado facial"],
        ),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO clinics
            (id, name, city, address, latitude, longitude, phone, whatsapp,
             services_json, verified, demo, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1)
        """,
        [
            (*clinic[:8], json.dumps(clinic[8], ensure_ascii=False))
            for clinic in clinics
        ],
    )


def _seed_demo_stores(connection: sqlite3.Connection) -> None:
    stores = [
        ("demo-store-inaquito", "Skin Market Iñaquito · Demo", "Quito", "Sector Iñaquito · ubicación demostrativa", -0.1780, -78.4814),
        ("demo-store-centro", "Dermocuidado Centro · Demo", "Quito", "Sector La Mariscal · ubicación demostrativa", -0.2015, -78.4902),
        ("demo-store-cumbaya", "Skin Lab Cumbayá · Demo", "Quito", "Sector Cumbayá · ubicación demostrativa", -0.2010, -78.4300),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO stores
            (id, name, city, address, latitude, longitude, verified, demo, active)
        VALUES (?, ?, ?, ?, ?, ?, 0, 1, 1)
        """,
        stores,
    )
    products = [
        ("cleanser-gentle", "Limpiador facial suave · Demo", "cleanser", "Limpieza sin exfoliantes intensos.", ["glicerina", "tensioactivos suaves"], ["gentle-care", "oil-balance"], "Mañana y noche; enjuagar con agua.", 12.90),
        ("moisturizer-barrier", "Hidratante con ceramidas · Demo", "moisturizer", "Crema cosmética para apoyar confort y barrera.", ["ceramidas", "glicerina"], ["hydration", "gentle-care", "fine-lines"], "Aplicar después de limpiar, mañana y noche.", 18.50),
        ("serum-niacinamide", "Sérum de niacinamida 5% · Demo", "serum", "Fórmula cosmética ligera para apariencia de tono y brillo.", ["niacinamida 5%", "pantenol"], ["tone", "pores", "oil-balance"], "Aplicar una vez al día; suspender si irrita.", 16.75),
        ("sunscreen-spf50", "Protector solar SPF 50 · Demo", "sunscreen", "Protección solar cosmética de amplio espectro.", ["filtros UV"], ["sun-protection", "tone", "fine-lines"], "Aplicar cada mañana y reaplicar según exposición.", 21.00),
        ("lotion-hyaluronic", "Loción hidratante ligera · Demo", "moisturizer", "Textura ligera para hidratación cosmética.", ["ácido hialurónico", "glicerina"], ["hydration", "texture"], "Aplicar sobre piel ligeramente húmeda.", 15.20),
    ]
    rows = []
    for store in stores:
        for product in products:
            rows.append(
                (
                    f"{store[0]}-{product[0]}",
                    store[0],
                    *product[1:4],
                    json.dumps(product[4], ensure_ascii=False),
                    json.dumps(product[5], ensure_ascii=False),
                    product[6],
                    product[7],
                )
            )
    connection.executemany(
        """
        INSERT OR IGNORE INTO products
            (id, store_id, name, category, description, ingredients_json,
             concerns_json, usage_text, price, currency, stock, demo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', 1, 1)
        """,
        rows,
    )


def _seed_real_retailers(connection: sqlite3.Connection) -> None:
    for retailer_id, name, website in RETAILERS:
        connection.execute(
            """
            INSERT INTO stores (
                id, name, city, address, latitude, longitude, verified, demo,
                active, website, online, retailer_code
            ) VALUES (?, ?, 'Ecuador', 'Tienda en línea', 0, 0, 0, 0, 1, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, website=excluded.website, online=1,
                retailer_code=excluded.retailer_code, active=1
            """,
            (retailer_id, name, website, retailer_id),
        )
    for product in REAL_PRODUCTS:
        (
            product_id,
            retailer_id,
            name,
            brand,
            category,
            step,
            price,
            source_url,
            skin_types,
            concerns,
            ingredients,
            usage,
            stock,
        ) = product
        connection.execute(
            """
            INSERT INTO products (
                id, store_id, name, category, description, ingredients_json,
                concerns_json, usage_text, price, currency, stock, demo, brand,
                source_url, skin_types_json, routine_step, verified_at,
                external_reference
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, 0, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, category=excluded.category,
                ingredients_json=excluded.ingredients_json,
                concerns_json=excluded.concerns_json,
                usage_text=excluded.usage_text,
                price=CASE WHEN products.verified_at IS NULL THEN excluded.price ELSE products.price END,
                stock=CASE WHEN products.verified_at IS NULL THEN excluded.stock ELSE products.stock END,
                brand=excluded.brand,
                source_url=excluded.source_url,
                skin_types_json=excluded.skin_types_json,
                routine_step=excluded.routine_step,
                verified_at=COALESCE(products.verified_at, excluded.verified_at),
                external_reference=1
            """,
            (
                product_id,
                retailer_id,
                name,
                category,
                f"Referencia oficial de {brand}.",
                json.dumps(ingredients, ensure_ascii=False),
                json.dumps(concerns, ensure_ascii=False),
                usage,
                price or 0,
                1 if stock is not False else 0,
                brand,
                source_url,
                json.dumps(skin_types, ensure_ascii=False),
                step,
                VERIFIED_AT,
            ),
        )


def _ensure_demo_slots(connection: sqlite3.Connection) -> None:
    from datetime import timedelta

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    connection.execute(
        """
        DELETE FROM appointment_slots
        WHERE available = 1 AND clinic_id LIKE 'demo-%'
        """
    )
    clinics = connection.execute("SELECT id FROM clinics WHERE active = 1").fetchall()
    for clinic in clinics:
        for day_offset in (1, 2, 4, 7):
            # 15:00 and 20:00 UTC correspond to 10:00 and 15:00 in Ecuador.
            for hour in (15, 20):
                starts_at = today + timedelta(days=day_offset, hours=hour)
                slot_id = f"{clinic['id']}-{starts_at.strftime('%Y%m%d%H%M')}"
                connection.execute(
                    """
                    INSERT OR IGNORE INTO appointment_slots
                        (id, clinic_id, starts_at, available)
                    VALUES (?, ?, ?, 1)
                    """,
                    (slot_id, clinic["id"], starts_at.isoformat()),
                )


def get_active_clinics() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, city, address, latitude, longitude, phone, whatsapp,
                   services_json, verified, demo
            FROM clinics
            WHERE active = 1
            """
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "city": row["city"],
            "address": row["address"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "phone": row["phone"],
            "whatsapp": row["whatsapp"],
            "services": json.loads(row["services_json"]),
            "verified": bool(row["verified"]),
            "demo": bool(row["demo"]),
        }
        for row in rows
    ]


def get_clinic(clinic_id: str) -> dict[str, Any] | None:
    return next(
        (clinic for clinic in get_active_clinics() if clinic["id"] == clinic_id),
        None,
    )


def get_active_stores() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, city, address, latitude, longitude, verified, demo,
                   website, online, retailer_code
            FROM stores WHERE active = 1
            """
        ).fetchall()
    return [
        dict(row)
        | {
            "verified": bool(row["verified"]),
            "demo": bool(row["demo"]),
            "online": bool(row["online"]),
        }
        for row in rows
    ]


def get_store(store_id: str) -> dict[str, Any] | None:
    return next((store for store in get_active_stores() if store["id"] == store_id), None)


def get_store_products(store_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, name, category, description, ingredients_json,
                   concerns_json, usage_text, price, currency, stock, demo,
                   brand, source_url, skin_types_json, routine_step, verified_at,
                   external_reference
            FROM products WHERE store_id = ? AND stock > 0
            """,
            (store_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "description": row["description"],
            "ingredients": json.loads(row["ingredients_json"]),
            "concerns": json.loads(row["concerns_json"]),
            "usage": row["usage_text"],
            "price": row["price"],
            "currency": row["currency"],
            "stock": row["stock"],
            "demo": bool(row["demo"]),
            "brand": row["brand"],
            "sourceUrl": row["source_url"],
            "skinTypes": json.loads(row["skin_types_json"] or "[]"),
            "routineStep": row["routine_step"],
            "verifiedAt": row["verified_at"],
            "externalReference": bool(row["external_reference"]),
        }
        for row in rows
    ]


def get_available_slots(clinic_id: str, limit: int = 20) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, starts_at FROM appointment_slots
            WHERE clinic_id = ? AND available = 1 AND starts_at > ?
            ORDER BY starts_at LIMIT ?
            """,
            (clinic_id, now, limit),
        ).fetchall()
    return [{"id": row["id"], "startsAt": row["starts_at"]} for row in rows]


def upsert_partner_clinic(clinic: dict[str, Any]) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO clinics (
                id, name, city, address, latitude, longitude, phone, whatsapp,
                services_json, verified, demo, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 1)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                city=excluded.city,
                address=excluded.address,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                phone=excluded.phone,
                whatsapp=excluded.whatsapp,
                services_json=excluded.services_json,
                verified=1,
                demo=0,
                active=1
            """,
            (
                clinic["id"],
                clinic["name"],
                clinic["city"],
                clinic["address"],
                clinic["latitude"],
                clinic["longitude"],
                clinic.get("phone"),
                clinic.get("whatsapp"),
                json.dumps(clinic["services"], ensure_ascii=False),
            ),
        )


def create_partner_slots(clinic_id: str, starts_at_values: list[str]) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    with connect() as connection:
        for starts_at in starts_at_values:
            slot_id = f"{clinic_id}-{uuid4().hex[:16]}"
            connection.execute(
                """
                INSERT INTO appointment_slots (id, clinic_id, starts_at, available)
                VALUES (?, ?, ?, 1)
                """,
                (slot_id, clinic_id, starts_at),
            )
            created.append({"id": slot_id, "startsAt": starts_at})
    return created


def list_partner_appointments(clinic_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.created_at, a.status, s.starts_at, l.id AS lead_id,
                   l.full_name, l.phone, l.email, l.preferred_channel
            FROM appointments a
            JOIN appointment_slots s ON s.id = a.slot_id
            JOIN leads l ON l.id = a.lead_id
            WHERE a.clinic_id = ?
            ORDER BY s.starts_at
            LIMIT ?
            """,
            (clinic_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "leadId": row["lead_id"],
            "createdAt": row["created_at"],
            "startsAt": row["starts_at"],
            "status": row["status"],
            "fullName": row["full_name"],
            "phone": row["phone"],
            "email": row["email"],
            "preferredChannel": row["preferred_channel"],
        }
        for row in rows
    ]


def update_partner_appointment(
    clinic_id: str, appointment_id: str, status: str
) -> bool:
    with connect() as connection:
        appointment = connection.execute(
            """
            SELECT slot_id FROM appointments
            WHERE id = ? AND clinic_id = ?
            """,
            (appointment_id, clinic_id),
        ).fetchone()
        if not appointment:
            return False
        connection.execute(
            "UPDATE appointments SET status = ? WHERE id = ?",
            (status, appointment_id),
        )
        connection.execute(
            """
            UPDATE leads SET status = ?
            WHERE id = (SELECT lead_id FROM appointments WHERE id = ?)
            """,
            (status, appointment_id),
        )
        if status == "cancelled":
            connection.execute(
                "UPDATE appointment_slots SET available = 1 WHERE id = ?",
                (appointment["slot_id"],),
            )
    return True


def create_appointment(
    *, lead_id: str, slot_id: str, clinic_id: str, session_id: str
) -> tuple[str, str, str]:
    appointment_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        slot = connection.execute(
            """
            SELECT starts_at FROM appointment_slots
            WHERE id = ? AND clinic_id = ? AND available = 1
            """,
            (slot_id, clinic_id),
        ).fetchone()
        if not slot:
            raise ValueError("El horario ya no está disponible.")
        connection.execute(
            "UPDATE appointment_slots SET available = 0 WHERE id = ?",
            (slot_id,),
        )
        connection.execute(
            """
            INSERT INTO appointments
                (id, lead_id, slot_id, clinic_id, session_id, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'requested')
            """,
            (appointment_id, lead_id, slot_id, clinic_id, session_id, created_at),
        )
    return appointment_id, created_at, slot["starts_at"]


def save_lead(
    *,
    clinic_id: str,
    session_id: str,
    full_name: str,
    phone: str,
    email: str | None,
    preferred_channel: str,
    preferred_time: str | None,
    latitude: float,
    longitude: float,
    distance_km: float,
    analysis_summary: dict[str, Any],
    consent_text: str,
) -> tuple[str, str]:
    lead_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO leads (
                id, clinic_id, session_id, created_at, status, full_name, phone,
                email, preferred_channel, preferred_time, latitude, longitude,
                distance_km, analysis_summary_json, consent_contact,
                consent_location, consent_results, consent_text
            ) VALUES (?, ?, ?, ?, 'new', ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, ?)
            """,
            (
                lead_id,
                clinic_id,
                session_id,
                created_at,
                full_name,
                phone,
                email,
                preferred_channel,
                preferred_time,
                latitude,
                longitude,
                distance_km,
                json.dumps(analysis_summary, ensure_ascii=False, separators=(",", ":")),
                consent_text,
            ),
        )
    return lead_id, created_at


def list_partner_leads(clinic_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT id, created_at, status, full_name, phone, email,
                   preferred_channel, preferred_time, distance_km,
                   analysis_summary_json
            FROM leads
            WHERE clinic_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (clinic_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "createdAt": row["created_at"],
            "status": row["status"],
            "fullName": row["full_name"],
            "phone": row["phone"],
            "email": row["email"],
            "preferredChannel": row["preferred_channel"],
            "preferredTime": row["preferred_time"],
            "distanceKm": row["distance_km"],
            "analysisSummary": json.loads(row["analysis_summary_json"]),
        }
        for row in rows
    ]


def delete_session_leads(session_id: str) -> int:
    with connect() as connection:
        slots = connection.execute(
            "SELECT slot_id FROM appointments WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        for slot in slots:
            connection.execute(
                "UPDATE appointment_slots SET available = 1 WHERE id = ?",
                (slot["slot_id"],),
            )
        connection.execute(
            "DELETE FROM appointments WHERE session_id = ?",
            (session_id,),
        )
        cursor = connection.execute(
            "DELETE FROM leads WHERE session_id = ?",
            (session_id,),
        )
    return cursor.rowcount


def delete_lead(session_id: str, lead_id: str) -> bool:
    with connect() as connection:
        appointment = connection.execute(
            "SELECT slot_id FROM appointments WHERE lead_id = ? AND session_id = ?",
            (lead_id, session_id),
        ).fetchone()
        if appointment:
            connection.execute(
                "UPDATE appointment_slots SET available = 1 WHERE id = ?",
                (appointment["slot_id"],),
            )
            connection.execute(
                "DELETE FROM appointments WHERE lead_id = ? AND session_id = ?",
                (lead_id, session_id),
            )
        cursor = connection.execute(
            "DELETE FROM leads WHERE id = ? AND session_id = ?",
            (lead_id, session_id),
        )
    return cursor.rowcount > 0
