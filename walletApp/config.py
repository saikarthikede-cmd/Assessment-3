import os
from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:Karthik@localhost:5432/walletdb",
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SQL_ECHO = _to_bool(os.getenv("SQL_ECHO"), False)
