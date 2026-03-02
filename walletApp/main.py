import time
from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.orm import Session

from walletApp import auth, crud, models, schemas
from walletApp.database import Base, engine, get_db
from walletApp.exceptions import register_exception_handlers
from walletApp.logging_config import get_logger, setup_logging
from walletApp.models import User

setup_logging()
logger = get_logger(__name__)
app = FastAPI(title="Wallet Core API")

Base.metadata.create_all(bind=engine)
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


@app.post("/users", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db, user.email)


@app.post("/auth/token", response_model=schemas.TokenResponse)
def issue_token(payload: schemas.AuthTokenRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, expires_in = auth.create_access_token(user.id, user.email)
    return schemas.TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


@app.post("/wallets/{user_id}", response_model=schemas.WalletResponse)
def create_wallet(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access(user_id, current_user.id)
    return crud.create_wallet(db, user_id)


@app.post("/wallets/{user_id}/credit", response_model=schemas.WalletResponse)
def credit(
    user_id: UUID,
    request: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access(user_id, current_user.id)
    return crud.credit_wallet(db, user_id, request.amount)


@app.post("/wallets/{user_id}/debit", response_model=schemas.WalletResponse)
def debit(
    user_id: UUID,
    request: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access(user_id, current_user.id)
    return crud.debit_wallet(db, user_id, request.amount)


@app.get("/wallets/{user_id}/balance", response_model=schemas.WalletResponse)
def balance(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access(user_id, current_user.id)
    return crud.get_balance(db, user_id)


@app.get("/wallets/{user_id}/ledger", response_model=List[schemas.LedgerResponse])
def ledger(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
):
    auth.authorize_user_access(user_id, current_user.id)
    return crud.get_ledger(db, user_id)
