import random
import time
from decimal import Decimal
from typing import Callable, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from walletApp.config import DB_TX_MAX_RETRIES, DB_TX_RETRY_BASE_DELAY
from walletApp.logging_config import get_logger
from walletApp.models import Ledger, User, Wallet

logger = get_logger(__name__)
RETRYABLE_SQLSTATES = {"40P01", "40001"}  # deadlock_detected, serialization_failure
T = TypeVar("T")


def _extract_sqlstate(exc: SQLAlchemyError) -> str | None:
    orig = getattr(exc, "orig", None)
    if not orig:
        return None
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _run_tx_with_retry(db: Session, operation_name: str, operation: Callable[[], T]) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            sqlstate = _extract_sqlstate(exc)
            should_retry = (
                sqlstate in RETRYABLE_SQLSTATES
                and attempt <= DB_TX_MAX_RETRIES
            )
            if should_retry:
                backoff = DB_TX_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                jitter = random.uniform(0, DB_TX_RETRY_BASE_DELAY) if DB_TX_RETRY_BASE_DELAY > 0 else 0
                sleep_for = backoff + jitter
                logger.warning(
                    "Retrying %s due to transient DB error | attempt=%s/%s sqlstate=%s sleep=%.3fs",
                    operation_name,
                    attempt,
                    DB_TX_MAX_RETRIES,
                    sqlstate,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue

            logger.exception(
                "Database error in %s | attempt=%s sqlstate=%s",
                operation_name,
                attempt,
                sqlstate,
            )
            raise HTTPException(status_code=500, detail="Transaction failed")


def create_user(db: Session, email: str):
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("User created | user_id=%s email=%s", user.id, user.email)
        return user
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate user create attempt | email=%s", email)
        raise HTTPException(status_code=400, detail="User already exists")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in create_user | email=%s", email)
        raise HTTPException(status_code=500, detail="Database error")


def create_wallet(db: Session, user_id: UUID):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        existing = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Wallet already exists")

        wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
        logger.info("Wallet created | user_id=%s wallet_id=%s", user_id, wallet.id)
        return wallet
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate wallet create attempt | user_id=%s", user_id)
        raise HTTPException(status_code=400, detail="Wallet already exists")
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in create_wallet | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")


def credit_wallet(db: Session, user_id: UUID, amount: Decimal):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    def _operation():
        update_result = db.execute(
            update(Wallet)
            .where(Wallet.user_id == user_id)
            .values(balance=Wallet.balance + amount)
            .returning(Wallet.id)
        ).first()
        if not update_result:
            raise HTTPException(status_code=404, detail="Wallet not found")

        wallet_id = update_result[0]
        entry = Ledger(wallet_id=wallet_id, type="credit", amount=amount)
        db.add(entry)

        db.commit()
        wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
        db.refresh(wallet)
        logger.info(
            "Wallet credited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet_id,
            amount,
            wallet.balance,
        )
        return wallet

    return _run_tx_with_retry(db, "credit_wallet", _operation)


def debit_wallet(db: Session, user_id: UUID, amount: Decimal):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    def _operation():
        # Single atomic update prevents race conditions across concurrent workers/instances.
        update_result = db.execute(
            update(Wallet)
            .where(Wallet.user_id == user_id, Wallet.balance >= amount)
            .values(balance=Wallet.balance - amount)
            .returning(Wallet.id)
        ).first()

        if not update_result:
            wallet_exists = db.query(Wallet.id).filter(Wallet.user_id == user_id).first()
            if not wallet_exists:
                raise HTTPException(status_code=404, detail="Wallet not found")
            raise HTTPException(status_code=400, detail="Insufficient balance")

        wallet_id = update_result[0]
        entry = Ledger(wallet_id=wallet_id, type="debit", amount=amount)
        db.add(entry)

        db.commit()
        wallet = db.query(Wallet).filter(Wallet.id == wallet_id).first()
        db.refresh(wallet)
        logger.info(
            "Wallet debited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet_id,
            amount,
            wallet.balance,
        )
        return wallet

    return _run_tx_with_retry(db, "debit_wallet", _operation)


def get_balance(db: Session, user_id: UUID):
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error in get_balance | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")


def get_ledger(db: Session, user_id: UUID):
    try:
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        return (
            db.query(Ledger)
            .filter(Ledger.wallet_id == wallet.id)
            .order_by(Ledger.created_at.desc())
            .all()
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error in get_ledger | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")
