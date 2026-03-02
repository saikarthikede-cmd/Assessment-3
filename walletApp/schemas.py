from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr


class AuthTokenRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    balance: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    amount: Decimal = Field(..., gt=0)


class LedgerResponse(BaseModel):
    id: UUID
    wallet_id: UUID
    type: str
    amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True
