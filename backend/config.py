import os
from pathlib import Path

APP_NAME = "DermaScan AI API"
APP_VERSION = "0.7.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.getenv("DERMASCAN_ENV", "development")
DATABASE_PATH = Path(
    os.getenv("DERMASCAN_DATABASE_PATH", str(PROJECT_ROOT / "data" / "dermascan.db"))
)
DATA_DIR = DATABASE_PATH.parent

MAX_UPLOAD_BYTES = int(os.getenv("DERMASCAN_MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_IMAGE_PIXELS = (
    int(os.getenv("DERMASCAN_MAX_IMAGE_MEGAPIXELS", "16")) * 1_000_000
)
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

RATE_LIMIT_REQUESTS = int(os.getenv("DERMASCAN_RATE_LIMIT_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("DERMASCAN_RATE_LIMIT_WINDOW_SECONDS", "600")
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DERMASCAN_CORS_ORIGINS",
        (
            "http://127.0.0.1:4187,http://localhost:4187,"
            "http://127.0.0.1:8000,http://localhost:8000,"
            "https://pablinvb.github.io"
        ),
    ).split(",")
    if origin.strip()
]
REFERRAL_TOKEN_SECRET = os.getenv(
    "DERMASCAN_REFERRAL_TOKEN_SECRET",
    "development-only-change-this-secret",
)
REFERRAL_TOKEN_TTL_SECONDS = int(
    os.getenv("DERMASCAN_REFERRAL_TOKEN_TTL_SECONDS", "3600")
)
PARTNER_API_KEY = os.getenv(
    "DERMASCAN_PARTNER_API_KEY",
    "development-partner-key",
)

if ENVIRONMENT == "production":
    if REFERRAL_TOKEN_SECRET == "development-only-change-this-secret":
        raise RuntimeError(
            "DERMASCAN_REFERRAL_TOKEN_SECRET debe configurarse en producción."
        )
    if PARTNER_API_KEY == "development-partner-key":
        raise RuntimeError("DERMASCAN_PARTNER_API_KEY debe configurarse en producción.")
