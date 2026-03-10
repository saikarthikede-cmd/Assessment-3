from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from walletApp.config import DATABASE_URL, SQL_ECHO
from walletApp.logging_config import get_logger

logger = get_logger(__name__)

engine = create_engine(DATABASE_URL, echo=SQL_ECHO, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

Base = declarative_base()


def ensure_schema_compatibility() -> None:
    # Backward-compatible DB patch for auth schema changes.
    from walletApp import models  # noqa: F401

    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR"))
        conn.execute(
            text("ALTER TABLE wallets ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0")
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Session error")
        raise
    finally:
        db.close()
