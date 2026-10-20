from datetime import datetime
from typing import Protocol

from trips.domain.geo import BoundingBox, LatLon
from trips.domain.types import Place, Route
from trips.domain.vehicle import VehicleProfile
from trips.domain.weather import HourlyWeather


class ProviderError(Exception):
    """An external API failed or returned something unusable.

    Messages must never contain API keys or full request URLs.
    """


class NoRouteError(ProviderError):
    """The router found no drivable route (e.g. across an ocean, or every option was avoided)."""


class Geocoder(Protocol):
    def search(self, query: str, *, limit: int) -> list[Place]:
        """Return up to `limit` US places matching a partial query, best match first."""
        ...


class RoutingProvider(Protocol):
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
        """Best route plus up to `max_alternatives` alternatives, with traffic for `depart_at`."""
        ...


class WeatherProvider(Protocol):
    def hourly(
        self, points: list[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, list[HourlyWeather]]:
        """Hourly forecasts from `start` to `end` (UTC, whole hours) for each point."""
        ...
