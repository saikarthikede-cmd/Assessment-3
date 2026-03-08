# Wallet Core API (Phase 1-3)

Basic FastAPI wallet service with PostgreSQL storage.

## Features
- Register and sign in with JWT auth
- Create one wallet per user
- Credit wallet
- Debit wallet
- Get balance
- Get transaction ledger
- Async FastAPI + Async SQLAlchemy
- Transaction-safe updates with retry on transient DB errors
- No negative balance (app + DB constraints)

## Tech Stack
- FastAPI
- SQLAlchemy
- PostgreSQL (`asyncpg` via SQLAlchemy async engine)
- Pydantic

## Project Structure
- `walletApp/config.py`
- `walletApp/database.py`
- `walletApp/models.py`
- `walletApp/schemas.py`
- `walletApp/crud.py`
- `walletApp/main.py`
- `walletApp/requirements.txt`

## Setup
```powershell
# from project root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\walletApp\requirements.txt
```

Create PostgreSQL database:
```sql
CREATE DATABASE walletdb;
```

Create `.env` in project root (already ignored by git):
```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://postgres:<your_password>@localhost:5432/walletdb
LOG_LEVEL=INFO
SQL_ECHO=false
DB_TX_MAX_RETRIES=3
DB_TX_RETRY_BASE_DELAY=0.05
```

You can use `.env.example` as template.

Optional: set custom DB URL from shell
```powershell
$env:DATABASE_URL="postgresql+psycopg://postgres:<your_password>@localhost:5432/walletdb"
```

## Run
```powershell
uvicorn walletApp.main:app --reload
```

Logging env options:
```powershell
$env:LOG_LEVEL="INFO"     # DEBUG, INFO, WARNING, ERROR
$env:SQL_ECHO="false"     # true to print SQL statements
```

Production safety:
- `APP_ENV=production` requires `DATABASE_URL` to be set.
- Never commit `.env` (contains secrets). Commit `.env.example` only.

Swagger UI:
- `http://127.0.0.1:8000/docs`

## Quick Verification Flow
1. `POST /auth/register` with `{ "email": "...", "password": "StrongPass!123" }`
2. `POST /auth/signin` with same credentials and copy `access_token`
3. In Swagger, click `Authorize` and enter `Bearer <token>`
4. `POST /wallets`
5. `POST /wallets/credit` with `{ "amount": "100.00" }`
6. `POST /wallets/debit` with `{ "amount": "40.00" }`
7. `GET /wallets/balance` => should be `60.00`
8. `GET /wallets/ledger` => should contain both credit and debit entries

## Phase 2: Concurrency Verification
Scenario:
- initial balance `100.00`
- `50` concurrent debit requests of `10.00`

Expected:
- `10` succeed
- `40` fail with insufficient balance
- final balance `0.00`
- exactly `10` debit ledger entries for `10.00`

Run:
```powershell
python -m walletApp.concurrency_check
```

The script prints `PHASE2_CONCURRENCY_CHECK: PASS` when concurrency consistency is correct.

## Phase 3: JWT Auth
Wallet endpoints require `Authorization: Bearer <token>`.

Sign in to issue token:
```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8000/auth/signin" `
  -ContentType "application/json" `
  -Body '{"email":"user@example.com","password":"StrongPass!123"}'
```

Use token for wallet APIs:
```powershell
$token = "<paste_access_token>"
$headers = @{ Authorization = "Bearer $token" }
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/wallets/balance" -Headers $headers
```

Automated Phase 3 check:
```powershell
python -m walletApp.phase3_auth_check
```

## Production Notes
- Centralized exception handling is enabled for:
  - `HTTPException`
  - request validation errors
  - SQLAlchemy/database errors
  - unexpected unhandled exceptions
- Request logs include method, path, status code, and request duration.
- CRUD operations log wallet/user transaction events and database failures.
- Passwords are hashed using `passlib` + `bcrypt`; raw passwords are never stored.

## Git Push Error Fix
If you see:
`fatal: 'origin' does not appear to be a git repository`

It means no remote named `origin` is configured.

Check remotes:
```powershell
git remote -v
```

Add your GitHub repo as origin:
```powershell
git remote add origin https://github.com/<your-username>/<your-repo>.git
```

Then push:
```powershell
git push -u origin main
```

If `origin` already exists but is wrong:
```powershell
git remote set-url origin https://github.com/<your-username>/<your-repo>.git
```
