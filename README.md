# Hurema HRMS

Hurema is a self-contained HRMS web app with:

- role-based authentication
- employee directory and profile management
- attendance marking and monthly logs
- leave application, approval, and balance allocation
- payroll structures, payrun generation, and payslips
- reports and admin audit logs

## Project Structure

- `frontend/` - static web app UI
- `backend/` - FastAPI backend with PostgreSQL persistence

## Run

Start the app from the repo root:

```powershell
npm start
```

The startup script will:

- create or reuse `backend/.venv313`
- install backend dependencies into that local Python 3.13 environment when needed
- create or reuse the PostgreSQL database from `backend/.env`
- serve the built frontend at `http://127.0.0.1:8000`

Then open:

- `http://127.0.0.1:8000`

For frontend-only development, run `npm run dev` in the repo root. Vite proxies `/api` requests to the backend on port `8000`.

## Deployment

Recommended:

- backend on Render
- PostgreSQL on Render
- frontend on Vercel

Why:

- the FastAPI backend handles auth cookies, PDF generation, uploads, and PostgreSQL access more naturally on Render
- the Vite frontend deploys very smoothly on Vercel

If you split deployment:

- set `VITE_API_BASE_URL` in the frontend to your backend URL, for example `https://your-api.onrender.com`
- set `CORS_ORIGINS` in the backend to include your Vercel domain and local development URLs

If you want the simplest single deployment, you can also deploy the whole app on Render because the backend already serves the built frontend from `frontend/dist`.

## Demo Accounts

- Admin: `admin@empay.local` / `Admin@123`
- HR Officer: `hr@empay.local` / `Hr@12345`
- Payroll Officer: `payroll@empay.local` / `Payroll@123`
- Employee: `employee@empay.local` / `Employee@123`

## Notes

- The default local setup uses PostgreSQL via `DATABASE_URL` in `backend/.env`.
- Demo data is seeded automatically on first run.
- The backend serves the built frontend from `frontend/dist`.

##Link
YT video : https://youtu.be/yOed0FNvE-Y?si=3LMBESDoHiV3Rr4P
