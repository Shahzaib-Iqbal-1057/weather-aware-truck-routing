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

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | Liveness check |
| GET | `/api/geocode/?q=` | US place autocomplete (cities, addresses, businesses) via TomTom Search. Cached for 24 h and rate limited, so the shared API quota is protected. |
| POST | `/api/trips/plan/` | Validates the trip and returns up to 3 candidate truck routes (cached 15 min, rate limited). Later stages add weather and risk. |

## How candidate routes are chosen

Routes come from the TomTom Routing API in truck mode (the "TomTom Maps" API family; the newer
Orbis family has no truck mode). We do not build a routing engine. We pick which routes to compare:

1. **Request.** Ask TomTom for the best truck route plus 3 alternatives, with the truck's weight,
   standard semi dimensions and departure time (so typical traffic for that hour is used).
2. **Filter and pick** (rules from Abraham, Delling, Goldberg & Werneck, *Alternative Routes in
   Road Networks*, SEA 2010, using the paper's values):
   - Always keep the fastest route.
   - Drop any route more than **25% slower** than the fastest (*bounded stretch*).
   - Then repeatedly add the route that **shares the least road** with those already chosen,
     skipping any that share **more than 80%** (*limited sharing*). Different roads mean different
     weather, which is what makes the comparison useful.
3. **Fill the gap.** If fewer than 3 routes survive, ask TomTom again while avoiding a ~140 km box
   on the middle of each chosen route (then on their first and second thirds), and repeat step 2
   on the combined set.
4. **Report honestly.** If 3 distinct routes still do not exist (short trips, or one sensible road),
   show the ones that do and say so.

Shared road is measured by sampling each route every 500 m and checking whether the sample lies on
the other route (~1 km grid). The paper applies the 25% limit to every part of a detour; a routing
API only returns whole routes, so it is applied to the whole trip. Requesting 3 alternatives rather
than TomTom's maximum of 5 halves the response time and gave the same choices in testing.

## Assumptions

- Region: United States only.
- Load weight is the truck's total (gross) weight in pounds, limited to standard legal loads
  (1,000–80,000 lb). Permit (overweight) loads are out of scope.
- Origin and destination are picked from autocomplete suggestions, so the app always knows the
  exact place (e.g. which of the many US "Springfield"s). For businesses, the location is the
  property's road entrance when TomTom provides one.
- The departure time is the local time at the origin (e.g. a truck leaving Denver at 8:00 means
  8:00 Denver time, wherever the dispatcher is). It is converted to UTC on the server.
- Departures may be up to 7 days ahead. Beyond 48 hours the app warns that the forecast is less
  reliable.
- The truck is a standard US tractor-trailer with a 53 ft trailer (13 ft 6 in tall, 8 ft 6 in
  wide, ~72 ft long, 5 axles), so routes respect low bridges and length limits. Only weight is
  entered by the user.
- Wind risk uses sustained wind speed; gusts are shown for information.
