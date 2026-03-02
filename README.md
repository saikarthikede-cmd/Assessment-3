# Wallet Core API (Phase 1)

Basic FastAPI wallet service with PostgreSQL storage.

## Features
- Create user
- Create wallet
- Credit wallet
- Debit wallet
- Get balance
- Get transaction ledger
- Transaction-safe updates
- No negative balance (app + DB constraints)

## Tech Stack
- FastAPI
- SQLAlchemy
- PostgreSQL (`psycopg`)
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
1. `POST /users`
2. Copy returned `id` as `USER_ID`
3. `POST /wallets/{USER_ID}`
4. `POST /wallets/{USER_ID}/credit` with `{ "amount": "100.00" }`
5. `POST /wallets/{USER_ID}/debit` with `{ "amount": "40.00" }`
6. `GET /wallets/{USER_ID}/balance` => should be `60.00`
7. `GET /wallets/{USER_ID}/ledger` => should contain both credit and debit entries

## Production Notes
- Centralized exception handling is enabled for:
  - `HTTPException`
  - request validation errors
  - SQLAlchemy/database errors
  - unexpected unhandled exceptions
- Request logs include method, path, status code, and request duration.
- CRUD operations log wallet/user transaction events and database failures.

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
