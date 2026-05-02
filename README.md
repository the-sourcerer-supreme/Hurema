# EmPay HRMS

EmPay is a self-contained HRMS web app with:

- role-based authentication
- employee directory and profile management
- attendance marking and monthly logs
- leave application, approval, and balance allocation
- payroll structures, payrun generation, and payslips
- reports and admin audit logs

## Project Structure

- `frontend/` - static web app UI
- `backend/` - Node.js HTTP server and JSON persistence

## Run

If `node` is available on your machine:

```bash
npm start
```

If you want to use the bundled runtime from this workspace:

```powershell
& 'C:\Users\acer\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'C:\Users\acer\Documents\New project\backend\server.js'
```

Then open:

- `http://localhost:3000`

## Demo Accounts

- Admin: `admin@empay.local` / `Admin@123`
- HR Officer: `hr@empay.local` / `Hr@12345`
- Payroll Officer: `payroll@empay.local` / `Payroll@123`
- Employee: `employee@empay.local` / `Employee@123`

## Notes

- The app persists data in `backend/data/db.json`.
- The JSON database is seeded automatically on first run.
- `backend/data/db.json` is ignored in git so each run can create its own local dataset.
