import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _to_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV == "production":
        raise RuntimeError("DATABASE_URL is required in production")
    DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/walletdb"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SQL_ECHO = _to_bool(os.getenv("SQL_ECHO"), False)
DB_TX_MAX_RETRIES = max(_to_int(os.getenv("DB_TX_MAX_RETRIES"), 3), 0)
DB_TX_RETRY_BASE_DELAY = max(_to_float(os.getenv("DB_TX_RETRY_BASE_DELAY"), 0.05), 0.0)
