from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from walletApp.config import DB_TX_MAX_RETRIES
from walletApp.logging_config import get_logger
from walletApp.models import Ledger, User, Wallet

logger = get_logger(__name__)

def _get_wallet_for_user(db: Session, user_id: UUID) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


def create_user(db: Session, email: str, hashed_password: str | None = None):
    try:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(email=email, hashed_password=hashed_password)
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
        user = db.scalar(select(User).where(User.id == user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        existing = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
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

    max_retries = max(DB_TX_MAX_RETRIES, 0)
    attempt = 0
    while True:
        try:
            wallet = _get_wallet_for_user(db, user_id)
            expected_version = wallet.version

            update_result = (
                db.execute(
                    update(Wallet)
                    .where(Wallet.user_id == user_id, Wallet.version == expected_version)
                    .values(balance=Wallet.balance + amount, version=Wallet.version + 1)
                    .returning(Wallet.id)
                )
            ).first()

            if not update_result:
                db.rollback()
                if attempt >= max_retries:
                    raise HTTPException(
                        status_code=409,
                        detail="Wallet updated by another request. Please retry.",
                    )
                attempt += 1
                continue

            wallet_id = update_result[0]
            db.add(Ledger(wallet_id=wallet_id, type="credit", amount=amount))

            db.commit()
            wallet = db.scalar(select(Wallet).where(Wallet.id == wallet_id))
            db.refresh(wallet)
            logger.info(
                "Wallet credited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
                user_id,
                wallet_id,
                amount,
                wallet.balance,
            )
            return wallet
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database error in credit_wallet | user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Database error")


def debit_wallet(db: Session, user_id: UUID, amount: Decimal):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    max_retries = max(DB_TX_MAX_RETRIES, 0)
    attempt = 0
    while True:
        try:
            wallet = _get_wallet_for_user(db, user_id)
            if wallet.balance < amount:
                raise HTTPException(status_code=400, detail="Insufficient balance")

            expected_version = wallet.version
            update_result = (
                db.execute(
                    update(Wallet)
                    .where(
                        Wallet.user_id == user_id,
                        Wallet.version == expected_version,
                        Wallet.balance >= amount,
                    )
                    .values(balance=Wallet.balance - amount, version=Wallet.version + 1)
                    .returning(Wallet.id)
                )
            ).first()

            if not update_result:
                db.rollback()
                refreshed = _get_wallet_for_user(db, user_id)
                if refreshed.balance < amount:
                    raise HTTPException(status_code=400, detail="Insufficient balance")
                if attempt >= max_retries:
                    raise HTTPException(
                        status_code=409,
                        detail="Wallet updated by another request. Please retry.",
                    )
                attempt += 1
                continue

            wallet_id = update_result[0]
            db.add(Ledger(wallet_id=wallet_id, type="debit", amount=amount))

            db.commit()
            wallet = db.scalar(select(Wallet).where(Wallet.id == wallet_id))
            db.refresh(wallet)
            logger.info(
                "Wallet debited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
                user_id,
                wallet_id,
                amount,
                wallet.balance,
            )
            return wallet
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database error in debit_wallet | user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Database error")


def get_balance(db: Session, user_id: UUID):
    try:
        wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
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
        wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        result = db.execute(
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
