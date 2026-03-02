from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from walletApp import crud, models, schemas
from walletApp.database import Base, engine, get_db

app = FastAPI(title="Wallet Core API")

Base.metadata.create_all(bind=engine)


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
