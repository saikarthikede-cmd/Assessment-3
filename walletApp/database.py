from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from walletApp.config import DATABASE_URL, SQL_ECHO
from walletApp.logging_config import get_logger

logger = get_logger(__name__)

engine = create_engine(DATABASE_URL, echo=SQL_ECHO, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_schema_compatibility() -> None:
    # Backward-compatible DB patch for auth schema changes.
    from walletApp import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR"))


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
