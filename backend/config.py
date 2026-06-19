from pathlib import Path

APP_NAME = "DermaScan AI API"
APP_VERSION = "0.2.0"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "dermascan.db"

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 10 * 60
