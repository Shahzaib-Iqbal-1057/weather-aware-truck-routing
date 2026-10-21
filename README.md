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
    lib/                shared helpers (time zones, formatting, risk colours)

Dockerfile              one image: builds the React app, runs Django under gunicorn
fly.toml                Fly.io deployment
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

## Deployment

The app is deployed on [Fly.io](https://fly.io) as **one service**: a single Docker image builds the
React app and runs Django under gunicorn, and Django serves the built app as well as the API (via
WhiteNoise: `index.html` at `/`, the hashed bundles under `/assets/` cached for a year). One
origin means no CORS and one URL to share.

Why it is set up this way:

- **Exactly one process, always running.** The weather budget and the caches live in that
  process's memory (see "Staying inside the free weather tier"), so gunicorn runs one worker
  with 8 threads, and Fly keeps one machine up with no autoscaling and no sleeping
  (`fly.toml`). A sleeping or second instance would reset or split the counts.
- **Its own outbound IP.** Open-Meteo's free tier limits by IP address. On hosts where many apps
  share outbound IPs, other people's weather requests would use up our allowance, so the app gets
  a static egress IP of its own.
- **Long requests are fine.** A long trip can take ~20 s of routing plus up to a minute waiting
  for weather allowance, so the gunicorn timeout is 120 s.
- **Secrets stay out of the repo.** `DJANGO_SECRET_KEY` and `TOMTOM_API_KEY` are Fly secrets. In
  production (`DJANGO_PRODUCTION=true`, set by the image) the app refuses to start without a real
  secret key. `DJANGO_NUM_PROXIES=1` makes rate limits use the client address Fly's proxy saw.

To deploy your own copy (after `fly auth login`; change the app name in `fly.toml` first):

```bash
fly apps create <app-name>
```

```bash
fly secrets set DJANGO_SECRET_KEY=<long random value> TOMTOM_API_KEY=<your key> --stage
```

```bash
fly ips allocate-egress --region ord
```

```bash
fly deploy --ha=false
```

`--ha=false` keeps it to one machine (Fly otherwise starts two). Fly skips giving the app a public
address when it already has an egress IP, so if the site doesn't answer after the first deploy, add
the free ones with `fly ips allocate-v4 --shared` and `fly ips allocate-v6`. To try the production image
locally: `docker build -t truck-routing .` and run it with `DJANGO_SECRET_KEY`,
`TOMTOM_API_KEY` and `DJANGO_ALLOWED_HOSTS=localhost` set, publishing port 8000.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health/` | Liveness check |
| GET | `/api/geocode/?q=` | US place autocomplete (cities, addresses, businesses) via TomTom Search. Cached for 24 h and rate limited, so the shared API quota is protected. |
| POST | `/api/trips/heatmap/` | Weather map for a planned trip (same body as the plan): risk level in every corridor cell for every hour from departure to 48 hours after it. Requested separately so the routes never wait for it. |
| POST | `/api/trips/plan/` | Validates the trip and returns up to 3 candidate truck routes, each with checkpoints, ETAs, required driver stops, the forecast and risk level at every checkpoint, per-route risk totals, the Moderate-or-worse stretches of each route for the map, and the recommended route with its reason (routes cached 1 h, weather 30 min, rate limited). |

Rate limits identify a client by the address its connection comes from, not by a header it can set
itself. Behind a host's load balancer, `DJANGO_NUM_PROXIES` says how many proxies to trust (see
`.env.example`).

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

- **Why 10 miles:** the brief lists "every 10 / 25 / 50 miles". We read that as a choice of
  sampling density and chose 10 miles for every trip, for the most detailed weather picture:
  forecast models resolve weather at roughly 3–13 km, so 10 miles (16 km) is close to the finest
  detail available, while 25 or 50 miles can step over a single thunderstorm cell. Weather for all
  checkpoints is fetched in batched requests, so the finer spacing costs little. (The API still
  accepts `spacing_mi` of 25 or 50.)
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
- **Wind = sustained wind at 10 m** for the risk rules, as in the brief; gusts are shown, and only
  very strong ones (55 mph or more) change the level (see the gust safeguard below).
- **Missing data is unknown, never calm.** An hour with any missing risk value is treated as "no
  forecast" for that checkpoint.
- **Fewer requests:** checkpoints are snapped to a 0.05° (~5 km) grid, so checkpoints of different
  routes on the same road share one lookup; requests are batched (100 locations each), cover only
  the hours the trip needs, and each grid point's forecast is cached for 30 minutes.
- **If the weather service fails,** the routes and ETAs are still shown with a clear note that
  weather risk can't be assessed — never a silent "all clear".
- An optional `OPEN_METEO_API_KEY` switches to Open-Meteo's paid endpoint (no rate limits) without
  code changes.

## Risk at each checkpoint

Each checkpoint's forecast is classified with the brief's risk table and load rules:

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (sustained) | < 25 mph | 25 – < 35 | 35 – < 45 | 45 – < 55 | **≥ 55** |
| Rain (incl. showers) | < 0.10 in/hr | 0.10 – < 0.25 | 0.25 – < 0.50 | 0.50 – **1.00** | **> 1.00** |
| Snow | < 0.5 in/hr | 0.5 – < 1.0 | 1.0 – < 2.0 | 2.0 – **3.0** | **> 3.0** |

- **Shared edges go to the more severe level.** The brief's ranges share their edge numbers
  (rain 0.25 appears under Moderate and High), so a value exactly on an edge takes the higher
  level: rain 0.25 in/hr is High, wind 35.0 mph is High. No Travel follows the table's wording:
  wind "≥ 55" (55.0 is No Travel), rain "> 1.00" and snow "> 3.0" (1.00 and 3.0 stay Severe).
- **Load rules** use sustained wind and the cargo weight: 45–54 mph with cargo over 30,000 lb is
  No Travel; 35–44 mph with cargo over 40,000 lb is Severe. "Over" is strict: exactly 30,000 lb
  does not trigger the first rule.
- **Gust safeguard (my addition):** gusts of 55 mph or more raise the wind level to at least High.
  The brief's table says only "wind"; we classify sustained wind as the table describes, but it is
  gusts that push high-sided trucks over, so a dangerous gust is never reported as Low or Moderate.
  It raises to High rather than No Travel because a gust is a burst, not a constant force.
- **The checkpoint's level is the worst of wind, rain and snow**, and the popup says what set it
  (e.g. "Severe risk: Wind 47.2 mph with cargo over 30,000 lb").
- **What you see is what was judged.** Values are rounded once (half up) to the precision shown —
  wind 0.1 mph, rain and snow 0.01 in/hr — and that rounded value is classified, so a popup can
  never show "25.0 mph" next to "Low".
- **No forecast means "Unknown", never "Low".**

## Choosing the recommended route

The brief asks to prefer, in order: fewest Severe miles, fewest High miles, lowest average risk,
shortest travel time. This is how I turned that into a rule, and why.

**Totals per route.** Each checkpoint stands for the road halfway to its neighbours, so a route's
Severe miles are the miles covered by its Severe checkpoints (likewise High and No Travel). Average
risk is the mile-weighted mean level (Low 0, Moderate 1, High 2, Severe 3, No Travel 4) over the
miles that have a forecast. Miles without a forecast are left out of every total and shown
separately: counting them as Low would hide risk, counting them as Severe would invent it.
Travel time is door-to-door, including the required driver stops.

**The rule.**

1. A route with any No Travel checkpoint is never recommended (it is still shown, with where and
   why). If every route has one, nothing is recommended and the app suggests a later departure.
   Without any weather data, nothing is recommended either.
2. Fewest **Severe miles**, then fewest **High miles**, compared exactly.
3. Lowest **average risk**, where a route counts as tied with the best if it is within **one
   checkpoint's worth**: 10 miles at one level higher, i.e. 10 ÷ the route's length in miles
   (0.036 on a 277-mile trip, 0.0125 on an 800-mile one). On trips under 40 miles one checkpoint
   is a large share of the route, so the margin is capped at a quarter of a level: a route that is
   Moderate end to end is never "practically the same" as one that is Low.
4. The **fastest** of the routes still tied.

The app shows the result as a "Recommended" badge, selects that route on the map, and gives a
one-line reason, e.g. "Route B: fewer Severe miles than A (0 vs 40); 1 h slower than A."

**How I arrived at it.** My first idea was to give every step a "practically equal" margin of 10
miles. Testing on real trips showed two things. First, most routes have no High or Severe miles at
all, so those steps are decided by genuine ties (0 vs 0) far more often than by small differences.
Second, a margin on Severe miles would treat a whole Severe checkpoint as noise, which a safety tool
should never do. So I dropped it: Severe and High miles move in whole-checkpoint steps already, and
I compare them exactly.

Average risk is different: it is a continuous number and two routes almost never tie, so without a
margin a meaningless difference would always beat travel time and the brief's fourth rule would
never apply. To size the margin from evidence rather than pick a number, I ran an 8-hour sweep on a
real trip through an active weather system (Las Vegas → Flagstaff, two routes, 42,000 lb cargo,
departures every 15 minutes) and measured how much a route's average moves when nothing real
changes:

- The typical non-zero change between departures 15 minutes apart was 0.036, exactly one
  checkpoint changing one level on that trip: a checkpoint's ETA crosses into the next forecast
  hour and its level flips.
- With no margin, the recommendation switched between the two routes 7 times in those 8 hours.
  With a one-checkpoint margin it switched 3 times, each at a real change in the weather. Larger
  margins (two checkpoints, or a fixed 0.05) gave the same result on that trip but would hide real
  differences on long trips.

So the margin is the smallest one that removes the flicker, and it follows from the 10-mile
checkpoint spacing rather than being tuned by hand. Travel time stays balanced against risk in
two ways: routes more than 25% slower than the fastest are never candidates (see route selection),
and when the weather is practically the same, the fastest route wins.

## Reading the map

- **Routes:** the selected route is blue and the alternatives gray, each with a label showing its
  door-to-door time. Click a line, its label or its card to select it. Lines and the weather map
  are drawn under the base map's place names, so a route never hides a town's name.
- **Risk on every route, not just the selected one.** Road at Moderate or worse is drawn in the
  risk colours *inside* the route's own line, so a stormy stretch on an alternative is visible
  without selecting it, and the blue or gray edge still says which route it belongs to. Each
  checkpoint covers the road halfway to its neighbours, and neighbouring checkpoints at the same
  level merge into one stretch; Low road stays a plain line, so the map isn't washed in green.
- **Checkpoint dots** on the selected route show the level at each 10-mile mark; hover or tap one
  for its ETA, weather and the rule that set the level. Zoomed out, 10-mile dots would overlap, so
  only every fifth Low dot is drawn (anything above Low always is).
- **Checkpoint details:** the same information as a table under the route list (with the driver's
  required stops in between), filterable to Moderate or worse. It works without a mouse,
  with a screen reader, and is quicker to scan than hovering dots.
- After planning, the form folds into a one-line trip summary ("Change trip" opens it again), so
  the recommendation and routes come first. On phones the map sits on top and the planner scrolls
  below it.
- Accessibility: every colour is named in the legend, the popups and the table; controls work by
  keyboard; focus moves to the results after planning; the slider's live status is quiet while it
  plays; map camera moves respect reduced-motion settings. Lighthouse (production build) scores
  100 for accessibility and best practices. Performance is 70 desktop / 83 mobile: almost all of
  the blocking time is MapLibre starting WebGL, which Lighthouse's headless Chrome renders in
  software; the planner itself loads first because the map is a separate, lazily loaded chunk.

## Weather map (0–48 h)

A colored layer around the routes shows weather risk across the trip corridor, for every hour from
the departure to 48 hours after it. Drag the slider, or press ▶ to play it like a radar loop.
A 🚚 marker shows where the truck would be at that hour on the selected route, so when the marker
sits in a colored area, that is when the truck drives through it. The map also shows weather
*between* checkpoints, e.g. a small storm cell that no checkpoint happens to land on.

- **Same risk rules as the checkpoints** (including the trip's cargo weight), so one legend explains
  both. Low is transparent: only weather that matters is colored.
- **The slider starts at the departure hour**, not at "now", so it always covers the whole trip,
  even for departures days ahead.
- **Corridor:** grid cells whose center is within 50 km of a route, on a fixed global grid, so
  trips through the same area share cached forecasts. Cells are 0.25° (~25 km) on shorter trips
  and coarsen to 0.5° or 1° to stay under 250 cells on long ones; storm systems that matter to
  trucks are tens to hundreds of km across.
- **Soft cells:** each cell is drawn as a blurred disc about one cell wide, so neighbouring cells
  blend into a radar-like field instead of a grid of squares. The forecast is still per cell; the
  blur only hides the grid.
- **Smooth by construction:** the browser gets every hour's level for every cell in one response.
  Moving the slider sets each cell's level for that hour as MapLibre *feature state*, which only
  repaints the map: no request, no data re-sent, and no re-tiling. The sidebar doesn't re-render
  on slider steps, and the truck marker is moved rather than rebuilt.
- **Loaded on demand** ("Show weather map", and "Hide" to turn it off again): it costs one weather
  location per cell, so trips where nobody opens it cost half as much. Planning a new trip turns
  it off again.
- **Still works after a while:** the map can be opened well after planning, even once a "leave
  now" departure has passed. It uses the plan's cached routes for up to an hour (less on a busy
  server); after that the routes are fetched again, for the departure time or for now if it has
  passed, so the corridor may differ slightly from the drawn routes. More than 24 hours after the
  departure, the trip has to be planned again.

**Staying inside the free weather tier.** Open-Meteo's free tier allows 600 locations per minute,
5,000 per hour and 10,000 per day, and every location in a batched request counts. All weather
requests go through one budget on the server: a request that would exceed the current minute waits
for the next one, and one that would exceed the hour or day is refused, so the app shows "weather
unavailable" rather than failing. A request waiting for the next minute doesn't hold up the
others. The weather map tells "busy, retrying shortly" apart from "allowance used up for now", and
only retries the first. When less than four maps' worth of the day's allowance is left, the weather
map uses a coarser grid. The counter lives in the server process's memory, so the app is deployed as
a single process. Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0).

## Assumptions

- Region: United States only (lower 48, Alaska and Hawaii). Autocomplete only offers US places.
  The API also checks coordinates against rough boxes around those three areas, which keeps out
  places like Paris but lets through border areas such as Toronto or Monterrey.
- **"Load weight" is the cargo (freight) weight**, 0–45,000 lb. An empty tractor with a 53 ft
  trailer already weighs about 35,000 lb, so if the input meant the whole truck, every semi would
  be over the brief's 30,000 lb threshold and the load rules would no longer distinguish light
  from heavy loads. The brief's load rules are applied to the cargo. For road and bridge limits the
  router is sent the truck's gross weight: 35,000 lb + cargo, at most the 80,000 lb federal limit
  (hence the 45,000 lb cargo maximum). Permit (overweight) loads are out of scope.
- Origin and destination are picked from autocomplete suggestions, so the app always knows the
  exact place (e.g. which of the many US "Springfield"s). For businesses, the location is the
  property's road entrance when TomTom provides one.
- The departure time is the local time at the origin (e.g. a truck leaving Denver at 8:00 means
  8:00 Denver time, wherever the dispatcher is). It is converted to UTC on the server.
- Departures may be up to 7 days ahead. Beyond 48 hours the app warns that the forecast is less
  reliable.
- The truck is a standard US tractor-trailer with a 53 ft trailer (13 ft 6 in tall, 8 ft 6 in
  wide, ~72 ft long, 5 axles), so routes respect low bridges and length limits. Dimensions are
  converted to metres rounded *up* to the next centimetre, so a clearance is never overstated.
- A departure time that doesn't exist locally (the hour skipped when clocks spring forward) is
  rejected. In the repeated hour when clocks fall back, the first occurrence is used.
- The truck is governed at **65 mph** (sent to the router as a 104 km/h maximum speed: the router
  takes whole km/h, so the value is rounded down to never exceed 65 mph). There is no federal
  truck speed cap (a 65 mph limiter rule was proposed and withdrawn in July 2025), but most large
  fleets use speed limiters and 65 mph is a common setting. Without a cap, routed truck speeds follow
  posted limits of up to 75–80 mph. The cap makes ETAs conservative.
- Wind risk uses sustained wind speed; gusts only count from 55 mph (raised to at least High).
- The driver is driving solo and starts the trip fresh (no hours already used that day or week);
  weekly 60/70-hour limits are not modelled.

## Known limitations

- Driver stops are placed exactly where the driving clock requires them; a real driver would stop
  at the nearest truck stop or rest area, a few miles earlier or later.
- TomTom's typical-traffic times assume the truck keeps driving. After a 10-hour rest the truck
  meets a different hour's traffic than the router assumed. The effect is small next to the rest
  itself.
- ETAs do not yet slow down for bad weather.
