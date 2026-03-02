import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from walletApp.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    wallet = relationship("Wallet", back_populates="user", uselist=False)


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallet_balance_non_negative"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Ledger", back_populates="wallet")


class Ledger(Base):
    __tablename__ = "ledger"
    __table_args__ = (
        CheckConstraint("type IN ('credit', 'debit')", name="ck_ledger_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallets.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    wallet = relationship("Wallet", back_populates="transactions")
