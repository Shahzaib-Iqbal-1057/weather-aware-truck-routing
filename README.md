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
| POST | `/api/trips/plan/` | Validates the trip and returns up to 3 candidate truck routes, each with checkpoints, ETAs, required driver stops and the forecast at every checkpoint (routes cached 15 min, weather 30 min, rate limited). Later stages add risk and the recommendation. |

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

## Checkpoints and ETAs

Weather is checked at **checkpoints every 10 miles** along each route, plus the start and the
destination (a regular checkpoint within 2 miles of the destination is skipped).

- **Why 10 miles:** the brief allows 10, 25 or 50. Forecast models resolve weather at roughly
  3–13 km, so 10 miles (16 km) is close to the finest detail available, while 25 or 50 miles can
  step over a single thunderstorm cell. Weather for all checkpoints is fetched in batched
  requests that stay within the free weather API tier at demo volumes.
- **Each checkpoint stands for the road halfway to its neighbours** (mile 20 covers miles 15–25;
  the start and destination cover the half-gaps next to them). The covered miles add up exactly to
  the route length, which is what "Severe miles" and "High miles" are counted from.
- **ETA = departure + driving time to the point + required driver stops before it.** Driving time
  comes from TomTom (truck speeds, typical traffic for the departure hour).

**Driver stops (US hours-of-service rules for property-carrying drivers):**

- a **30-minute break after 8 hours of driving**;
- a **10-hour rest after 11 hours of driving**, after which a new shift starts and the pattern
  repeats.

The 30-minute break is not driving time, so a shift is 11 h of driving within 11.5 h, inside the
14-hour on-duty window. Stops are placed where the driving clock reaches those limits. A route's
**door-to-door time and arrival include these stops**; route cards show driving and rest time
separately.

The 11-hour limit has no grace period, so a trip slightly over it is a cliff: 11 h 14 min of
driving means a 10-hour rest a mile or two before the destination. The app shows this as the law
requires and says so on the route card, rather than quietly ignoring a few minutes over the limit.

**Times are shown on the departure city's clock** (e.g. "6:50 AM CDT") so a trip that crosses time
zones reads on one consistent clock.

## Weather at each checkpoint

Forecasts come from [Open-Meteo](https://open-meteo.com) (free, no key; it picks the best model
for each place, which in the US is NOAA's ~3 km HRRR for the near term and coarser global models
further out).

- **Matched to the hour the truck is there.** Each hourly record holds the hour before it, so a
  truck at a checkpoint at 9:40 uses the 10:00 record (rain and snow for 9:00–10:00, wind at
  10:00). Values are not interpolated between hours: hourly totals cannot be split meaningfully,
  and it would suggest more precision than the forecast has.
- **Units match the risk table:** wind in mph, rain and snow in inches per hour.
- **Rain = rain + showers.** Open-Meteo reports steady (stratiform) rain and convective showers
  separately; both fall on the road, and thunderstorm showers are where the dangerous rates come
  from, so they are added, not averaged.
- **Wind = sustained wind at 10 m** for the risk rules; gusts are shown for information.
- **Missing data is unknown, never calm.** An hour with any missing risk value is treated as "no
  forecast" for that checkpoint.
- **Fewer requests:** checkpoints are snapped to a 0.05° (~5 km) grid, so checkpoints of different
  routes on the same road share one lookup; requests are batched (100 locations each), cover only
  the hours the trip needs, and each grid point's forecast is cached for 30 minutes.
- **If the weather service fails,** the routes and ETAs are still shown with a clear note that
  weather risk can't be assessed — never a silent "all clear".
- An optional `OPEN_METEO_API_KEY` switches to Open-Meteo's paid endpoint (no rate limits) without
  code changes.

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
- The truck is governed at **65 mph** (sent to the router as a 104 km/h maximum speed: the router
  takes whole km/h, so the value is rounded down to never exceed 65 mph). There is no federal
  truck speed cap (a 65 mph limiter rule was proposed and withdrawn in July 2025), but most large
  fleets use speed limiters and 65 mph is a common setting. Without a cap, routed truck speeds follow
  posted limits of up to 75–80 mph. The cap makes ETAs conservative.
- Wind risk uses sustained wind speed; gusts are shown for information.
- The driver is driving solo and starts the trip fresh (no hours already used that day or week);
  weekly 60/70-hour limits are not modelled.

## Known limitations

- Driver stops are placed exactly where the driving clock requires them; a real driver would stop
  at the nearest truck stop or rest area, a few miles earlier or later.
- TomTom's typical-traffic times assume the truck keeps driving. After a 10-hour rest the truck
  meets a different hour's traffic than the router assumed. The effect is small next to the rest
  itself.
- ETAs do not yet slow down for bad weather.
