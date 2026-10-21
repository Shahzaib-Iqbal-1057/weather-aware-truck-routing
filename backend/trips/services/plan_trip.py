"""Runs the pipeline for one trip. Each stage is added here as it is built (see README)."""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import caches
from django.utils import timezone

from trips.domain.candidates import MAX_ROUTES, detour_boxes, select_routes, shortfall_reason
from trips.domain.recommendation import Recommendation, recommend
from trips.domain.risk import CheckpointRisk, classify, rounded_for_rules
from trips.domain.route_totals import RouteTotals, route_totals
from trips.domain.timeline import RouteTimeline, build_timeline
from trips.domain.trip_request import TripRequest
from trips.domain.types import Route
from trips.domain.vehicle import standard_semi
from trips.domain.weather import HourlyWeather
from trips.providers.base import NoRouteError, ProviderError, RoutingProvider, WeatherProvider
from trips.providers.tomtom_routing import TomTomRouter
from trips.services.weather import weather_at

logger = logging.getLogger(__name__)

# Long enough that a weather map opened well after planning uses the same routes as the plan.
ROUTE_CACHE_SECONDS = 60 * 60
# TomTom's response time grows with each alternative (NYC→Chicago: ~11 s for 3, ~22 s for 5).
# 3 alternatives (4 routes) was enough for the selection in testing; the fallback covers the rest.
REQUESTED_ALTERNATIVES = 3
# Where to place avoid-boxes on the chosen routes when fewer than 3 distinct routes came back:
# first the middle of each route, then (if still short) its first and second thirds.
FALLBACK_ATTEMPTS: tuple[tuple[float, ...], ...] = ((0.5,), (1 / 3, 2 / 3))


WEATHER_UNAVAILABLE_NOTE = (
    "Weather is unavailable right now, so weather risk can't be assessed for these routes."
)


@dataclass(frozen=True)
class PlannedRoute:
    id: str  # "A", "B", "C" in order of travel time
    route: Route
    timeline: RouteTimeline
    # Aligned with timeline.checkpoints. None = no forecast, so the risk is unknown.
    weather: list[HourlyWeather | None]  # rounded once; these exact values are shown and judged
    risk: list[CheckpointRisk | None]
    totals: RouteTotals


@dataclass(frozen=True)
class TripPlan:
    trip: TripRequest
    # Fastest first. More driving never means fewer rest stops, so this is also arrival order.
    routes: list[PlannedRoute]
    recommendation: Recommendation
    weather_available: bool = True
    notes: list[str] = field(default_factory=list)


def get_router() -> RoutingProvider:
    return TomTomRouter(settings.TOMTOM_API_KEY)


def plan_trip(
    trip: TripRequest,
    *,
    router: RoutingProvider | None = None,
    weather: WeatherProvider | None = None,
) -> TripPlan:
    """Stages 1–6: routes, checkpoints and stops, weather and risk, totals, recommendation.

    Raises NoRouteError if the trip cannot be driven at all. If the weather service fails, the
    routes are still returned, with weather marked unavailable.
    """
    routes, shortfall = _candidate_routes(trip, router or get_router())
    timelines = [build_timeline(route, trip.departure_utc, trip.spacing_mi) for route in routes]

    notes = []
    if shortfall:
        noun = "route" if len(routes) == 1 else "routes"
        notes.append(f"Only {len(routes)} distinct truck {noun} for this trip: {shortfall}.")

    checkpoint_times = [(c.position, c.eta) for timeline in timelines for c in timeline.checkpoints]
    try:
        forecasts = weather_at(checkpoint_times, provider=weather)
        weather_available = True
    except ProviderError:
        logger.exception("Weather lookup failed")
        forecasts = [None] * len(checkpoint_times)
        weather_available = False
        notes.append(WEATHER_UNAVAILABLE_NOTE)

    # Stage 4: round once, then classify those same values.
    forecasts = [rounded_for_rules(w) if w is not None else None for w in forecasts]
    risks = [classify(w, trip.cargo_weight_lb) if w is not None else None for w in forecasts]

    planned, start = [], 0
    for index, (route, timeline) in enumerate(zip(routes, timelines, strict=True)):
        end = start + len(timeline.checkpoints)
        route_risks = risks[start:end]
        planned.append(
            PlannedRoute(
                id=chr(ord("A") + index),
                route=route,
                timeline=timeline,
                weather=forecasts[start:end],
                risk=route_risks,
                totals=route_totals(route.length_m, timeline, route_risks),  # Stage 5
            )
        )
        start = end

    # Stage 6
    recommendation = recommend(
        [p.totals for p in planned], [p.id for p in planned], trip.spacing_mi
    )
    return TripPlan(
        trip=trip,
        routes=planned,
        recommendation=recommendation,
        weather_available=weather_available,
        notes=notes,
    )


def trip_routes(trip: TripRequest, *, router: RoutingProvider | None = None) -> list[Route]:
    """The trip's candidate routes (the same, cached ones the plan used)."""
    routes, _ = _candidate_routes(trip, router or get_router())
    return routes


def _candidate_routes(trip: TripRequest, router: RoutingProvider) -> tuple[list[Route], str | None]:
    """The chosen routes, and why there are fewer than MAX_ROUTES (None if there are not)."""
    cache_key = _route_cache_key(trip)
    route_cache = caches["routes"]
    cached = route_cache.get(cache_key)
    if cached is not None:
        return cached

    vehicle = standard_semi(trip.cargo_weight_lb)
    # The router rejects departures in the past; Stage 0 allows a few minutes of grace.
    depart_at = max(trip.departure_utc, timezone.now() + timedelta(minutes=1))

    def fetch(avoid_areas=None) -> list[Route]:
        return router.routes(
            trip.origin,
            trip.destination,
            depart_at=depart_at,
            vehicle=vehicle,
            max_alternatives=REQUESTED_ALTERNATIVES if avoid_areas is None else 0,
            avoid_areas=avoid_areas,
        )

    pool = fetch()
    selected = select_routes(pool)
    fallback_failed = False
    for fractions in FALLBACK_ATTEMPTS:
        if len(selected) >= MAX_ROUTES:
            break
        boxes = detour_boxes(selected, fractions)
        if not boxes:
            break
        try:
            pool += fetch(avoid_areas=boxes)
        except NoRouteError:
            continue  # every way round was blocked; try boxes elsewhere
        except ProviderError:
            # e.g. rate limit or timeout: keep the good routes we already have.
            logger.warning("Detour routing failed; returning %d route(s)", len(selected))
            fallback_failed = True
            break
        selected = select_routes(pool)

    shortfall = None
    if fallback_failed:
        shortfall = "the search for more routes failed, please try again shortly"
    elif len(selected) < MAX_ROUTES:
        shortfall = shortfall_reason(pool, selected)

    result = (selected, shortfall)
    # A transient failure should not pin a short list of routes in the cache.
    if not fallback_failed:
        route_cache.set(cache_key, result, ROUTE_CACHE_SECONDS)
    return result


def _route_cache_key(trip: TripRequest) -> str:
    departure_slot: datetime = trip.departure_utc.replace(
        minute=trip.departure_utc.minute // 15 * 15, second=0, microsecond=0
    )
    parts = (
        f"{trip.origin.lat:.5f},{trip.origin.lon:.5f}",
        f"{trip.destination.lat:.5f},{trip.destination.lon:.5f}",
        departure_slot.isoformat(),
        str(trip.cargo_weight_lb),
    )
    return "routes:" + hashlib.sha256("|".join(parts).encode()).hexdigest()
