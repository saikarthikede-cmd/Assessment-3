from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from walletApp.config import ASYNC_DATABASE_URL, SQL_ECHO
from walletApp.logging_config import get_logger

logger = get_logger(__name__)

engine = create_async_engine(ASYNC_DATABASE_URL, echo=SQL_ECHO, pool_pre_ping=True)

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

Base = declarative_base()


async def ensure_schema_compatibility() -> None:
    # Backward-compatible DB patch for auth schema changes.
    from walletApp import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR"))


async def get_db():
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Session error")
        raise
    finally:
        await db.close()
