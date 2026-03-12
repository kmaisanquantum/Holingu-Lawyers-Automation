# Holingu Lawyers — Analytical Repository
## Port Moresby, Papua New Guinea

Full-stack legal document management system built for Holingu Lawyers.

---

## Stack

| Layer    | Technology                    |
|----------|-------------------------------|
| Backend  | FastAPI (Python 3.11)         |
| Database | SQLite (persistent disk)      |
| Frontend | Vanilla HTML/JS + Chart.js    |
| Deploy   | Render.com (Singapore region) |
| Currency | PGK — Papua New Guinean Kina  |

---

## Project Structure

```
holingu-lawyers/
├── render.yaml              ← Render deployment config
├── Procfile                 ← Fallback start command
├── requirements.txt         ← Python dependencies
├── README.md
│
├── backend/
│   ├── app.py               ← FastAPI app logic
│   ├── database.py          ← SQLite init + seed data
│   └── routers/
│       ├── matters.py       ← /api/matters
│       ├── documents.py     ← /api/documents
│       ├── clients.py       ← /api/clients
│       ├── users.py         ← /api/users
│       ├── risks.py         ← /api/risks
│       ├── deadlines.py     ← /api/deadlines
│       ├── analytics.py     ← /api/analytics
│       └── vault.py         ← /api/vault (search)
│
├── frontend/
│   └── index.html           ← Full UI (served by FastAPI)
│
├── database/
│   └── schema.sql           ← Full SQL schema reference
│
└── uploads/                 ← PDF upload storage
```

---

## API Endpoints

| Method | Endpoint                         | Description                          |
|--------|----------------------------------|--------------------------------------|
| GET    | /health                          | Health check                         |
| GET    | /api/matters                     | List all matters (filterable)        |
| GET    | /api/matters/{ref}               | Get matter + all related data        |
| POST   | /api/matters                     | Create new matter                    |
| PATCH  | /api/matters/{ref}               | Update matter                        |
| GET    | /api/documents                   | List documents                       |
| GET    | /api/documents/{ref}             | Document + extracted data            |
| POST   | /api/documents/upload/{matter}   | Upload PDF to vault                  |
| GET    | /api/clients                     | List clients (IPA/TIN search)        |
| GET    | /api/risks?status=open           | Open risk flags (by severity)        |
| PATCH  | /api/risks/{id}                  | Update risk flag status              |
| GET    | /api/deadlines?days_ahead=30     | Upcoming deadlines                   |
| GET    | /api/deadlines/alerts/pending    | Deadlines needing alert emails       |
| GET    | /api/analytics/dashboard         | Full dashboard payload               |
| GET    | /api/analytics/value             | Matter value breakdown               |
| GET    | /api/vault/search?q=indemnity    | Full-text vault search               |
| GET    | /api/vault/stats                 | Document pipeline statistics         |

**Interactive API docs:** `/docs` (Swagger UI)

---

## Deploy to Render

### Option A — render.yaml (recommended)

1. Push this folder to a GitHub repository
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml` and configure everything

### Option B — Manual setup

1. New Web Service on Render
2. **Runtime:** Python 3
3. **Region:** Singapore (closest to Port Moresby)
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. **Add Disk:** Mount path `/data`, 1 GB

### Environment Variables

| Key             | Value                          |
|-----------------|--------------------------------|
| DATABASE_PATH   | ./database/holingu_vault.db    |
| UPLOAD_DIR      | ./uploads                      |

---

## Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API server
uvicorn main:app --reload --port 8000

# 3. Open the app
open http://localhost:8000

# 4. View API docs
open http://localhost:8000/docs
```

The database is created and seeded automatically on first run.

---

## Database

**13 tables:** users · clients · matters · documents · property_references ·
extracted_parties · extracted_financials · extracted_dates · risk_flags ·
generated_documents · document_embeddings · audit_log · matter_notes

**Seed data includes:**
- 5 users (3 partners, 1 associate, 1 admin)
- 7 clients (IPA registered PNG entities)
- 7 matters (HLG-2024-001 to 007) — deeds, deals, mining, contracts
- 7 documents with extraction results
- 7 open risk flags (1 critical, 3 high, 3 medium)
- 8 deadlines with alert triggers
- 8 financial terms in PGK

---

## Governing Law

All document templates and precedents conform to:
- Laws of Papua New Guinea (Consolidation Acts)
- Land Act (PNG) Chapter 185
- Mining Act (PNG) 1992
- Companies Act (PNG) 1997
- Lands Registration Act (PNG) Chapter 191
- Internal Revenue Commission (IRC) requirements

---

*Holingu Lawyers · Level 2, Mogoru Moto · Champion Parade · Port Moresby NCD · Papua New Guinea*
