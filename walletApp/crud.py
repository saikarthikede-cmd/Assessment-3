from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from walletApp.models import Ledger, User, Wallet


def create_user(db: Session, email: str):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_wallet(db: Session, user_id: UUID):
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
    return wallet


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
        return wallet
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
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
        return wallet
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Transaction failed")


def get_balance(db: Session, user_id: UUID):
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return wallet


def get_ledger(db: Session, user_id: UUID):
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    return (
        db.query(Ledger)
        .filter(Ledger.wallet_id == wallet.id)
        .order_by(Ledger.created_at.desc())
        .all()
    )
