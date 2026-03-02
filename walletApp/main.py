import time
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import EmailStr
from sqlalchemy.orm import Session

from walletApp import auth, crud, models, schemas
from walletApp.database import ensure_schema_compatibility, get_db
from walletApp.exceptions import register_exception_handlers
from walletApp.logging_config import get_logger, setup_logging
from walletApp.models import User

setup_logging()
logger = get_logger(__name__)
app = FastAPI(title="Wallet Core API")

ensure_schema_compatibility()
register_exception_handlers(app)


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
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    hashed_password = auth.hash_password(payload.password)
    return crud.create_user(db, payload.email, hashed_password)


@app.post("/auth/signin", response_model=schemas.TokenResponse, tags=["Auth"])
def signin(payload: schemas.AuthTokenRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_in = auth.create_access_token(user.id, user.email)
    return schemas.TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@app.post("/wallets/{email}", response_model=schemas.WalletResponse)
def create_wallet(
    email: EmailStr,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access_by_email(email, current_user.email)
    return crud.create_wallet(db, current_user.id)


@app.post("/wallets/{email}/credit", response_model=schemas.WalletResponse)
def credit(
    email: EmailStr,
    request: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access_by_email(email, current_user.email)
    return crud.credit_wallet(db, current_user.id, request.amount)


@app.post("/wallets/{email}/debit", response_model=schemas.WalletResponse)
def debit(
    email: EmailStr,
    request: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access_by_email(email, current_user.email)
    return crud.debit_wallet(db, current_user.id, request.amount)


@app.get("/wallets/{email}/balance", response_model=schemas.WalletResponse)
def balance(
    email: EmailStr,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access_by_email(email, current_user.email)
    return crud.get_balance(db, current_user.id)


@app.get("/wallets/{email}/ledger", response_model=List[schemas.LedgerResponse])
def ledger(
    email: EmailStr,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access_by_email(email, current_user.email)
    return crud.get_ledger(db, current_user.id)
