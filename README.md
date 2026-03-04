# NEXRAY — Operations Platform

Private internal operations platform for multi-entity textile operations.  
Built for Premium Projects, B2B Wholesale, and DTC E-Commerce entities.

---

## Features

- **12 Modules**: Dashboard, Outbound Queue, Cut Transactions, Tags & Labels, Lots & Rolls, Warehouses, Movement Ledger, Approvals, Findings, Integrations, Users & RBAC, Audit Log
- **3 Entities**: Premium Projects (ent-01), B2B Wholesale (ent-02), DTC E-Commerce (ent-03)
- **3 Warehouses**: Manila Central (wh-01), Cebu Hub (wh-02), Aurora Facility (wh-03)
- **6 RBAC Roles**: system_admin, inventory_admin, warehouse_operator, warehouse_lead, manager, accounting_operator
- **Light/Dark Mode** toggle
- **SQLite Database** with WAL mode, 25+ tables
- **Demo data** auto-seeded on first boot

---

## Tech Stack

- **Backend**: Python / FastAPI + Uvicorn
- **Frontend**: Vanilla HTML / CSS / JavaScript
- **Database**: SQLite (auto-created on startup)
- **Fonts**: Inter + JetBrains Mono (via Google Fonts CDN)

---

## Deploy to Railway

### Option A: One-Click (GitHub → Railway)

1. **Push this folder to a GitHub repo**:
   ```bash
   cd nexray-railway
   git init
   git add .
   git commit -m "NEXRAY initial deploy"
   git remote add origin https://github.com/YOUR_USERNAME/nexray.git
   git push -u origin main
   ```

2. **Go to [railway.app](https://railway.app)** → Sign in with GitHub

3. **Click "New Project" → "Deploy from GitHub Repo"**

4. **Select your `nexray` repo** — Railway auto-detects Python and uses `railway.toml`

5. **Railway will**:
   - Install dependencies from `requirements.txt`
   - Run the start command from `railway.toml`
   - Assign a public URL (e.g., `https://nexray-production-xxxx.up.railway.app`)

6. **Generate a domain**: Go to Settings → Networking → Generate Domain

7. **Open your URL** — NEXRAY is live with demo data.

### Option B: Railway CLI

1. **Install Railway CLI**:
   ```bash
   npm install -g @railway/cli
   # or
   brew install railway
   ```

2. **Login and deploy**:
   ```bash
   cd nexray-railway
   railway login
   railway init
   railway up
   ```

3. **Generate a domain**:
   ```bash
   railway domain
   ```

---

## Local Development

```bash
cd nexray-railway
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## Environment Variables (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Server port (Railway sets this automatically) |
| `NEXRAY_DB_PATH` | `nexray.db` | SQLite database file path |

---

## Project Structure

```
nexray-railway/
├── server.py           # FastAPI backend (all API routes + DB init + demo seeding)
├── requirements.txt    # Python dependencies
├── Procfile            # Process declaration
├── railway.toml        # Railway deployment config
├── .gitignore          # Git ignore rules
├── README.md           # This file
└── static/
    ├── index.html      # Main HTML shell
    ├── base.css        # Reset + design tokens
    ├── style.css       # Component styles
    └── app.js          # Frontend application logic
```

---

## API Endpoints

All endpoints are prefixed with `/api/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/dashboard?entity=ent-01` | Dashboard KPIs & charts |
| GET | `/api/outbound` | Outbound queue |
| POST | `/api/outbound` | Create outbound order |
| GET | `/api/cuts` | Cut transactions |
| POST | `/api/cuts` | Create cut transaction |
| GET | `/api/tags` | Tags & labels |
| POST | `/api/tags` | Create tag |
| GET | `/api/lots` | Lots & rolls |
| POST | `/api/lots` | Create lot |
| GET | `/api/warehouses` | Warehouse list |
| GET | `/api/movements` | Movement ledger |
| POST | `/api/movements` | Record movement |
| GET | `/api/approvals` | Approvals queue |
| PATCH | `/api/approvals` | Approve/reject |
| GET | `/api/findings` | Findings log |
| POST | `/api/findings` | Create finding |
| GET | `/api/integrations` | Integration configs |
| GET | `/api/users` | Users & RBAC |
| POST | `/api/users` | Create user |
| GET | `/api/audit` | Audit log |
| POST | `/api/seed` | Re-seed demo data |

---

## Notes

- **SQLite** is used for simplicity. On Railway's ephemeral filesystem, data resets on each deploy. For persistent data, attach a Railway volume or migrate to PostgreSQL.
- **Demo data** is auto-seeded on first startup (if tables are empty).
- **No authentication** is currently implemented — this is a private internal tool. Add auth middleware before exposing publicly.
