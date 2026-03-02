from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from walletApp.config import DATABASE_URL, SQL_ECHO
from walletApp.logging_config import get_logger

logger = get_logger(__name__)

engine = create_engine(DATABASE_URL, echo=SQL_ECHO, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


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
