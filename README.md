# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route based on weather, load weight
and travel time.

## Project structure

```
backend/                Django + Django REST Framework
  config/               settings (from env vars), root urls, wsgi
  trips/
    domain/             pure pipeline logic: no Django, no network
    providers/          adapters for routing, geocoding and weather APIs
    services/           runs the pipeline stages in order
    api/                thin HTTP layer: validate, call a service, serialize
  tests/                mirrors trips/

frontend/               Vite + React + TypeScript
  src/
    api/                fetch client, response types, query hooks
    features/           trip-form, map, route-summary, heatmap
    components/         shared UI
    lib/                shared helpers (risk colors, formatting)
```

## Local development

Requirements: Python 3.13+, Node 24+.

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp ../.env.example .env
.venv/bin/python manage.py runserver
```

API runs at http://127.0.0.1:8000/api/ (health check: `/api/health/`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173. In dev, Vite forwards `/api` to Django, so no CORS setup is needed.

## Quality checks

| | Backend (`backend/`) | Frontend (`frontend/`) |
|---|---|---|
| Lint | `.venv/bin/ruff check .` | `npm run lint` |
| Format | `.venv/bin/ruff format .` | `npm run format` |
| Types | — | `npm run typecheck` |
| Tests | `.venv/bin/pytest` | `npm test` |

## Assumptions

- Region: United States only.
- Load weight is the truck's total (gross) weight in pounds, limited to standard legal loads
  (≤ 80,000 lb). Permit (overweight) loads are out of scope.
- Wind risk uses sustained wind speed; gusts are shown for information.
