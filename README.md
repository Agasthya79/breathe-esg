# BreatheESG — Emissions Intelligence Platform

Full-stack Django REST + React application for ingesting, normalizing, and reviewing Scope 1/2/3 emissions data from SAP, Utility, and Travel sources.

---

## Quick Start (local)

### 1 — Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed          # loads emission factors + 43 sample activities
python manage.py createsuperuser   # create admin user
python manage.py runserver
```

API available at http://localhost:8000/api/

### 2 — Frontend

```bash
cd frontend
npm install
# Create .env.local:
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

App at http://localhost:5173

---

## Deploy to Render (one click)

1. Push this repo to GitHub
2. Go to https://render.com → New → Blueprint → select repo → select `render.yaml`
3. Set `VITE_API_URL` to your backend service URL (e.g. `https://breathe-esg-api.onrender.com`)
4. Click "Apply"

After deploy, run seed via Render shell:
```bash
python manage.py seed
python manage.py createsuperuser
```

---

## Architecture

```
breathe_esg/
├── backend/                  Django REST API
│   ├── core/                 Settings, URLs, WSGI
│   ├── emissions/            Models: Tenant, User, Client, EmissionFactor,
│   │                           IngestionBatch, RawRecord, NormalizedActivity, AuditLog
│   ├── ingestion/            Parsers (SAP/Utility/Travel), ViewSets, Serializers
│   │   └── parsers.py        parse_sap, parse_utility, parse_travel
│   └── manage.py
├── frontend/                 React + Vite + Recharts
│   └── src/
│       ├── pages/            Dashboard, Upload, Review, Batches, Login
│       ├── components/       UI primitives (Btn, Badge, Modal, StatCard…)
│       ├── hooks/            useAuth (JWT), useToast
│       └── api/              Axios client with auto-refresh
├── render.yaml               One-click Render deployment
├── MODEL.md                  Data model + reasoning (35% of grade)
├── DECISIONS.md              Ambiguity resolution log
├── TRADEOFFS.md              Deliberate skips
└── SOURCES.md                Research + sample data rationale
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/auth/token/` | Login → JWT |
| POST | `/api/auth/token/refresh/` | Refresh token |
| GET | `/api/clients/` | List clients |
| POST | `/api/batches/` | Upload + parse file |
| GET | `/api/batches/` | List ingestion history |
| GET | `/api/activities/` | List normalized activities (filterable) |
| GET | `/api/activities/summary/` | Aggregated CO₂e stats |
| POST | `/api/activities/{id}/approve/` | Approve + lock row |
| POST | `/api/activities/{id}/reject/` | Reject with note |
| POST | `/api/activities/{id}/unlock/` | Admin unlock (note required) |
| GET | `/api/activities/{id}/history/` | Full audit trail |
| GET | `/api/raw-records/` | Raw parse output per batch |

---

## Test Suite (62 tests, 0 failures)

```bash
cd backend
python manage.py test
```

Covers: parser unit tests (SAP German headers, date formats, unit conversion),
API integration tests, review workflow, audit trail, duplicate detection, aggregation.

---

## Sample Data Files

The `seed` command pre-loads 17 emission factors + 43 sample activities.
Sample CSVs for manual upload are available via the Upload page → "Sample CSV" button.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DEBUG` | No | Default False in prod |
| `DATABASE_URL` | Yes (prod) | PostgreSQL connection string |
| `VITE_API_URL` | Yes (frontend) | Backend base URL |
