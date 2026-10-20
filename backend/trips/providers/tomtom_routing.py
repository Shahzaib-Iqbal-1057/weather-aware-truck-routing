"""Truck routing via TomTom Routing API, Calculate Route (TomTom Maps / "Genesis", v1).

Orbis Routing has no truck mode, which is why the Genesis API is used.
"""

from datetime import UTC, datetime
from math import floor
from typing import Any

import requests

from trips.domain.geo import BoundingBox, haversine_meters
from trips.domain.types import Place, Route
from trips.domain.vehicle import VehicleProfile
from trips.providers.base import NoRouteError, ProviderError

ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
MAX_ALTERNATIVES = 5
MAX_AVOID_AREAS = 10
_NO_ROUTE_CODES = {"NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE"}


class TomTomRouter:
    def __init__(
        self, api_key: str, *, session: requests.Session | None = None, timeout: float = 30
    ):
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout

    def routes(
        self,
        origin: Place,
        destination: Place,
        *,
        depart_at: datetime,
        vehicle: VehicleProfile,
        max_alternatives: int,
        avoid_areas: list[BoundingBox] | None = None,
    ) -> list[Route]:
        if not self._api_key:
            raise ProviderError("TomTom API key is not configured.")

        url = ROUTE_URL.format(
            locations=f"{origin.lat},{origin.lon}:{destination.lat},{destination.lon}"
        )
        params = _query_params(self._api_key, depart_at, vehicle, max_alternatives)
        try:
            if avoid_areas:
                # Avoid areas can only be sent in a POST body.
                response = self._session.post(
                    url, params=params, json=_avoid_body(avoid_areas), timeout=self._timeout
                )
            else:
                response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"TomTom routing request failed: {type(exc).__name__}") from None

        if response.status_code != 200:
            _raise_for_error(response)
        return parse_routes(response.json())


def _query_params(
    api_key: str, depart_at: datetime, vehicle: VehicleProfile, max_alternatives: int
) -> list[tuple[str, str | int | float]]:
    return [
        ("key", api_key),
        ("travelMode", "truck"),
        ("vehicleCommercial", "true"),
        ("vehicleWeight", round(vehicle.weight_kg)),
        ("vehicleHeight", vehicle.height_m),
        ("vehicleWidth", vehicle.width_m),
        ("vehicleLength", vehicle.length_m),
        ("vehicleNumberOfAxles", vehicle.axles),
        # TomTom takes whole km/h; round down so the cap never exceeds the stated speed.
        ("vehicleMaxSpeed", floor(vehicle.max_speed_kmh)),
        ("departAt", depart_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        ("traffic", "true"),
        ("maxAlternatives", min(max_alternatives, MAX_ALTERNATIVES)),
        ("routeRepresentation", "polyline"),
        ("extendedRouteRepresentation", "distance"),
        ("extendedRouteRepresentation", "travelTime"),
    ]


def _avoid_body(areas: list[BoundingBox]) -> dict[str, Any]:
    return {
        "avoidAreas": {
            "rectangles": [
                {
                    "southWestCorner": {"latitude": box.south, "longitude": box.west},
                    "northEastCorner": {"latitude": box.north, "longitude": box.east},
                }
                for box in areas[:MAX_AVOID_AREAS]
            ]
        }
    }


def _raise_for_error(response: requests.Response) -> None:
    try:
        code = response.json().get("detailedError", {}).get("code", "")
    except ValueError:
        code = ""
    if code in _NO_ROUTE_CODES:
        raise NoRouteError("No route found.")
    raise ProviderError(f"TomTom routing failed with HTTP {response.status_code} {code}".strip())


def parse_routes(payload: dict[str, Any]) -> list[Route]:
    return [_parse_route(route) for route in payload.get("routes", [])]


def _parse_route(data: dict[str, Any]) -> Route:
    points: list[tuple[float, float]] = []
    for leg in data["legs"]:
        for point in leg["points"]:
            lat_lon = (point["latitude"], point["longitude"])
            if not points or points[-1] != lat_lon:  # legs share their joining point
                points.append(lat_lon)

    summary = data["summary"]
    distances, times = _interpolate_progress(points, data.get("progress", []), summary)
    return Route(
        points=points,
        distances_m=distances,
        times_s=times,
        traffic_delay_s=float(summary.get("trafficDelayInSeconds", 0)),
    )


def _interpolate_progress(
    points: list[tuple[float, float]], progress: list[dict[str, Any]], summary: dict[str, Any]
) -> tuple[list[float], list[float]]:
    """Cumulative distance and time for every point.

    TomTom reports exact values only at some points ("progress" entries). Between two of them,
    we spread the reported distance and time in proportion to the straight-line gaps between points.
    """
    known = {
        int(p["pointIndex"]): (float(p["distanceInMeters"]), float(p["travelTimeInSeconds"]))
        for p in progress
        if "distanceInMeters" in p and "travelTimeInSeconds" in p
    }
    known.setdefault(0, (0.0, 0.0))
    known[len(points) - 1] = (
        float(summary["lengthInMeters"]),
        float(summary["travelTimeInSeconds"]),
    )

    anchors = sorted(i for i in known if i < len(points))
    distances = [0.0] * len(points)
    times = [0.0] * len(points)
    for start, end in zip(anchors, anchors[1:], strict=False):
        (d0, t0), (d1, t1) = known[start], known[end]
        gaps = [haversine_meters(points[i], points[i + 1]) for i in range(start, end)]
        total = sum(gaps)
        walked = 0.0
        distances[start], times[start] = d0, t0
        for offset, gap in enumerate(gaps, start=1):
            walked += gap
            share = walked / total if total > 0 else offset / len(gaps)
            distances[start + offset] = d0 + share * (d1 - d0)
            times[start + offset] = t0 + share * (t1 - t0)
    return distances, times
