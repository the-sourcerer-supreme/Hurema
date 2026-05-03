# EmPay Backend

This backend is a FastAPI service for the EmPay HRMS app. The local setup uses PostgreSQL only.

## Local Run

From the repo root:

```powershell
npm start
```

That launcher will:

- create or reuse `backend/.venv313`
- install `backend/requirements.txt` into that repo-local environment when needed
- create or reuse the target PostgreSQL database from `backend/.env`
- start Uvicorn from `backend/`

The app is served at:

- `http://127.0.0.1:8000`

## Database

Default local database:

```env
DATABASE_URL=postgresql+asyncpg://postgres:Hash123@localhost:5432/empay_db
```

## Demo Accounts

- Admin: `admin@empay.local` / `Admin@123`
- HR Officer: `hr@empay.local` / `Hr@12345`
- Payroll Officer: `payroll@empay.local` / `Payroll@123`
- Employee: `employee@empay.local` / `Employee@123`
