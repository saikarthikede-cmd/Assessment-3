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


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV == "production":
        raise RuntimeError("DATABASE_URL is required in production")
    DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/walletdb"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SQL_ECHO = _to_bool(os.getenv("SQL_ECHO"), False)
