import time
from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from sqlalchemy.orm import Session

from walletApp import crud, models, schemas
from walletApp.database import Base, engine, get_db
from walletApp.exceptions import register_exception_handlers
from walletApp.logging_config import get_logger, setup_logging

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


@app.post("/wallets/{user_id}", response_model=schemas.WalletResponse)
def create_wallet(user_id: UUID, db: Session = Depends(get_db)):
    return crud.create_wallet(db, user_id)


@app.post("/wallets/{user_id}/credit", response_model=schemas.WalletResponse)
def credit(user_id: UUID, request: schemas.TransactionCreate, db: Session = Depends(get_db)):
    return crud.credit_wallet(db, user_id, request.amount)


@app.post("/wallets/{user_id}/debit", response_model=schemas.WalletResponse)
def debit(user_id: UUID, request: schemas.TransactionCreate, db: Session = Depends(get_db)):
    return crud.debit_wallet(db, user_id, request.amount)


@app.get("/wallets/{user_id}/balance", response_model=schemas.WalletResponse)
def balance(user_id: UUID, db: Session = Depends(get_db)):
    return crud.get_balance(db, user_id)


@app.get("/wallets/{user_id}/ledger", response_model=List[schemas.LedgerResponse])
def ledger(user_id: UUID, db: Session = Depends(get_db)):
    return crud.get_ledger(db, user_id)
