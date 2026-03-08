import asyncio
import random
from decimal import Decimal
from typing import Awaitable, Callable, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _run_tx_with_retry(db: AsyncSession, operation_name: str, operation: Callable[[], Awaitable[T]]) -> T:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await operation()
        except HTTPException:
            await db.rollback()
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            sqlstate = _extract_sqlstate(exc)
            should_retry = sqlstate in RETRYABLE_SQLSTATES and attempt <= DB_TX_MAX_RETRIES
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
                await asyncio.sleep(sleep_for)
                continue

            logger.exception(
                "Database error in %s | attempt=%s sqlstate=%s",
                operation_name,
                attempt,
                sqlstate,
            )
            raise HTTPException(status_code=500, detail="Transaction failed")


async def create_user(db: AsyncSession, email: str, hashed_password: str | None = None):
    try:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(email=email, hashed_password=hashed_password)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("User created | user_id=%s email=%s", user.id, user.email)
        return user
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        logger.warning("Duplicate user create attempt | email=%s", email)
        raise HTTPException(status_code=400, detail="User already exists")
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Database error in create_user | email=%s", email)
        raise HTTPException(status_code=500, detail="Database error")


async def create_wallet(db: AsyncSession, user_id: UUID):
    try:
        user = await db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        existing = await db.scalar(select(Wallet).where(Wallet.user_id == user_id))
        if existing:
            raise HTTPException(status_code=400, detail="Wallet already exists")

        wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        db.add(wallet)
        await db.commit()
        await db.refresh(wallet)
        logger.info("Wallet created | user_id=%s wallet_id=%s", user_id, wallet.id)
        return wallet
    except HTTPException:
        await db.rollback()
        raise
    except IntegrityError:
        await db.rollback()
        logger.warning("Duplicate wallet create attempt | user_id=%s", user_id)
        raise HTTPException(status_code=400, detail="Wallet already exists")
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("Database error in create_wallet | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")


async def credit_wallet(db: AsyncSession, user_id: UUID, amount: Decimal):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    async def _operation():
        update_result = (
            await db.execute(
                update(Wallet)
                .where(Wallet.user_id == user_id)
                .values(balance=Wallet.balance + amount)
                .returning(Wallet.id)
            )
        ).first()
        if not update_result:
            raise HTTPException(status_code=404, detail="Wallet not found")

        wallet_id = update_result[0]
        db.add(Ledger(wallet_id=wallet_id, type="credit", amount=amount))

        await db.commit()
        wallet = await db.scalar(select(Wallet).where(Wallet.id == wallet_id))
        await db.refresh(wallet)
        logger.info(
            "Wallet credited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet_id,
            amount,
            wallet.balance,
        )
        return wallet

    return await _run_tx_with_retry(db, "credit_wallet", _operation)


async def debit_wallet(db: AsyncSession, user_id: UUID, amount: Decimal):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    async def _operation():
        update_result = (
            await db.execute(
                update(Wallet)
                .where(Wallet.user_id == user_id, Wallet.balance >= amount)
                .values(balance=Wallet.balance - amount)
                .returning(Wallet.id)
            )
        ).first()

        if not update_result:
            wallet_exists = await db.scalar(select(Wallet.id).where(Wallet.user_id == user_id))
            if not wallet_exists:
                raise HTTPException(status_code=404, detail="Wallet not found")
            raise HTTPException(status_code=400, detail="Insufficient balance")

        wallet_id = update_result[0]
        db.add(Ledger(wallet_id=wallet_id, type="debit", amount=amount))

        await db.commit()
        wallet = await db.scalar(select(Wallet).where(Wallet.id == wallet_id))
        await db.refresh(wallet)
        logger.info(
            "Wallet debited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet_id,
            amount,
            wallet.balance,
        )
        return wallet

    return await _run_tx_with_retry(db, "debit_wallet", _operation)


async def get_balance(db: AsyncSession, user_id: UUID):
    try:
        wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id))
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return wallet
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error in get_balance | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")


async def get_ledger(db: AsyncSession, user_id: UUID):
    try:
        wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id))
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        result = await db.execute(
            select(Ledger)
            .where(Ledger.wallet_id == wallet.id)
            .order_by(Ledger.created_at.desc())
        )
        return result.scalars().all()
    except HTTPException:
        raise
    except SQLAlchemyError:
        logger.exception("Database error in get_ledger | user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Database error")
