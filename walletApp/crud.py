from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from walletApp.logging_config import get_logger
from walletApp.models import Ledger, User, Wallet

logger = get_logger(__name__)


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
    try:
        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        wallet.balance = wallet.balance + amount
        entry = Ledger(wallet_id=wallet.id, type="credit", amount=amount)
        db.add(entry)

        db.commit()
        db.refresh(wallet)
        logger.info(
            "Wallet credited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet.id,
            amount,
            wallet.balance,
        )
        return wallet
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in credit_wallet | user_id=%s amount=%s", user_id, amount)
        raise HTTPException(status_code=500, detail="Transaction failed")


def debit_wallet(db: Session, user_id: UUID, amount: Decimal):
    try:
        wallet = (
            db.query(Wallet)
            .filter(Wallet.user_id == user_id)
            .with_for_update()
            .first()
        )
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        if wallet.balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient balance")

        wallet.balance = wallet.balance - amount
        entry = Ledger(wallet_id=wallet.id, type="debit", amount=amount)
        db.add(entry)

        db.commit()
        db.refresh(wallet)
        logger.info(
            "Wallet debited | user_id=%s wallet_id=%s amount=%s new_balance=%s",
            user_id,
            wallet.id,
            amount,
            wallet.balance,
        )
        return wallet
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error in debit_wallet | user_id=%s amount=%s", user_id, amount)
        raise HTTPException(status_code=500, detail="Transaction failed")


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
