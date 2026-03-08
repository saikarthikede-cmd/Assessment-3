import time
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from walletApp import auth, crud, schemas
from walletApp.database import ensure_schema_compatibility, get_db
from walletApp.exceptions import register_exception_handlers
from walletApp.logging_config import get_logger, setup_logging
from walletApp.models import User

setup_logging()
logger = get_logger(__name__)
app = FastAPI(title="Wallet Core API")

register_exception_handlers(app)


@app.on_event("startup")
async def startup_event() -> None:
    await ensure_schema_compatibility()


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "Request served | method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.post("/auth/register", response_model=schemas.UserResponse, tags=["Auth"])
async def register(payload: schemas.RegisterRequest, db: AsyncSession = Depends(get_db)):
    hashed_password = auth.hash_password(payload.password)
    return await crud.create_user(db, payload.email, hashed_password)


@app.post("/auth/signin", response_model=schemas.TokenResponse, tags=["Auth"])
async def signin(payload: schemas.AuthTokenRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_in = auth.create_access_token(user.id, user.email)
    return schemas.TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@app.post("/wallets", response_model=schemas.WalletResponse, tags=["Wallet"])
async def create_wallet(
    current_user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.create_wallet(db, current_user.id)


@app.post("/wallets/credit", response_model=schemas.WalletResponse, tags=["Wallet"])
async def credit(
    request: schemas.TransactionCreate,
    current_user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.credit_wallet(db, current_user.id, request.amount)


@app.post("/wallets/debit", response_model=schemas.WalletResponse, tags=["Wallet"])
async def debit(
    request: schemas.TransactionCreate,
    current_user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.debit_wallet(db, current_user.id, request.amount)


@app.get("/wallets/balance", response_model=schemas.WalletResponse, tags=["Wallet"])
async def balance(
    current_user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_balance(db, current_user.id)


@app.get("/wallets/ledger", response_model=List[schemas.LedgerResponse], tags=["Wallet"])
async def ledger(
    current_user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_ledger(db, current_user.id)
