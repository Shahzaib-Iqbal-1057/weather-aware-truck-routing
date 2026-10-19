"""Runs the pipeline for one trip. Each stage is added here as it is built (see README)."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from trips.domain.candidates import MAX_ROUTES, detour_boxes, select_routes
from trips.domain.trip_request import TripRequest
from trips.domain.types import Route
from trips.domain.vehicle import standard_semi
from trips.providers.base import NoRouteError, RoutingProvider
from trips.providers.tomtom_routing import TomTomRouter

ROUTE_CACHE_SECONDS = 15 * 60
# TomTom's response time grows with each alternative (NYC→Chicago: ~11 s for 3, ~22 s for 5).
# 3 alternatives (4 routes) was enough for the selection in testing; the fallback covers the rest.
REQUESTED_ALTERNATIVES = 3
# Where to place avoid-boxes on the chosen routes when fewer than 3 distinct routes came back:
# first the middle of each route, then (if still short) its first and second thirds.
FALLBACK_ATTEMPTS: tuple[tuple[float, ...], ...] = ((0.5,), (1 / 3, 2 / 3))


@dataclass(frozen=True)
class TripPlan:
    trip: TripRequest
    routes: list[Route]
    notes: list[str] = field(default_factory=list)


def get_router() -> RoutingProvider:
    return TomTomRouter(settings.TOMTOM_API_KEY)


def plan_trip(trip: TripRequest, *, router: RoutingProvider | None = None) -> TripPlan:
    """Stage 1: candidate routes. Raises NoRouteError if the trip cannot be driven at all."""
    routes = _candidate_routes(trip, router or get_router())
    notes = []
    if len(routes) < MAX_ROUTES:
        noun = "route exists" if len(routes) == 1 else "routes exist"
        notes.append(f"Only {len(routes)} distinct truck {noun} for this trip.")
    return TripPlan(trip=trip, routes=routes, notes=notes)


def _candidate_routes(trip: TripRequest, router: RoutingProvider) -> list[Route]:
    cache_key = _route_cache_key(trip)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    vehicle = standard_semi(trip.weight_lb)
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
        selected = select_routes(pool)

    cache.set(cache_key, selected, ROUTE_CACHE_SECONDS)
    return selected


def _route_cache_key(trip: TripRequest) -> str:
    departure_slot: datetime = trip.departure_utc.replace(
        minute=trip.departure_utc.minute // 15 * 15, second=0, microsecond=0
    )
    parts = (
        f"{trip.origin.lat:.5f},{trip.origin.lon:.5f}",
        f"{trip.destination.lat:.5f},{trip.destination.lon:.5f}",
        departure_slot.isoformat(),
        str(trip.weight_lb),
    )
    return "routes:" + hashlib.sha256("|".join(parts).encode()).hexdigest()
