"""Stage 3 (and the Stage 8 weather map): hourly forecasts for grid points, cached and budgeted."""

import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.core.cache import cache

from trips.domain.geo import LatLon
from trips.domain.weather import HourlyWeather, forecast_hour, grid_point
from trips.providers.base import WeatherProvider
from trips.providers.open_meteo import OpenMeteoWeather
from trips.services.weather_budget import get_budget

# Forecasts update roughly hourly. Nothing older than this is ever served.
CACHE_SECONDS = 30 * 60
CHECKPOINT_CACHE = "weather"


@dataclass(frozen=True)
class _CachedForecast:
    """One fetch for one grid point. Replaced wholesale on refetch, never merged, so every record
    in it is exactly as old as `fetched_at`."""

    fetched_at: float
    start: datetime
    end: datetime
    records: dict[datetime, HourlyWeather]

    def fresh(self, now: float) -> bool:
        return now - self.fetched_at < CACHE_SECONDS

    def answers(self, hour: datetime, now: float) -> bool:
        """True if this fetch is fresh and covered `hour` (even if the hour had no data)."""
        return self.fresh(now) and self.start <= hour <= self.end


def get_weather_provider() -> WeatherProvider:
    return OpenMeteoWeather(settings.OPEN_METEO_API_KEY)


def weather_at(
    checkpoint_times: list[tuple[LatLon, datetime]], *, provider: WeatherProvider | None = None
) -> list[HourlyWeather | None]:
    """Forecast for each (position, ETA), in order. None where the forecast has no data.

    Positions are snapped to the weather grid, so nearby checkpoints (e.g. on road shared by two
    routes) share one lookup. Raises ProviderError if the weather service fails.
    """
    wanted = [(grid_point(position), forecast_hour(eta)) for position, eta in checkpoint_times]
    hours_by_point: dict[LatLon, set[datetime]] = defaultdict(set)
    for point, hour in wanted:
        hours_by_point[point].add(hour)
    records = hourly_records(hours_by_point, cache_name=CHECKPOINT_CACHE, provider=provider)
    return [records[point].get(hour) for point, hour in wanted]


def hourly_records(
    hours_by_point: dict[LatLon, set[datetime]],
    *,
    cache_name: str,
    provider: WeatherProvider | None = None,
) -> dict[LatLon, dict[datetime, HourlyWeather]]:
    """Hourly forecasts covering the requested hours at each point (from cache when fresh).

    `cache_name` separates grids of different resolution, so their points never collide.
    """
    now = _now()
    keys = {point: f"{cache_name}:{point[0]:.4f},{point[1]:.4f}" for point in hours_by_point}
    cached = cache.get_many(list(keys.values()))
    forecasts: dict[LatLon, _CachedForecast] = {
        point: entry for point, key in keys.items() if (entry := cached.get(key)) is not None
    }

    stale = sorted(
        point
        for point, hours in hours_by_point.items()
        if point not in forecasts or not all(forecasts[point].answers(h, now) for h in hours)
    )
    if stale:
        # Also re-cover hours a still-fresh entry had, so one entry keeps serving both trips.
        spans = [
            hour
            for point in stale
            for hour in (
                *hours_by_point[point],
                *(
                    (forecasts[point].start, forecasts[point].end)
                    if point in forecasts and forecasts[point].fresh(now)
                    else ()
                ),
            )
        ]
        start, end = min(spans), max(spans)
        fetched = _fetch_within_budget(stale, start, end, provider or get_weather_provider())
        fresh = {
            point: _CachedForecast(now, start, end, {r.hour: r for r in fetched.get(point, [])})
            for point in stale
        }
        cache.set_many({keys[point]: entry for point, entry in fresh.items()}, CACHE_SECONDS)
        forecasts.update(fresh)

    return {point: forecasts[point].records for point in hours_by_point}


def _fetch_within_budget(
    points: list[LatLon], start: datetime, end: datetime, provider: WeatherProvider
) -> dict[LatLon, list]:
    budget = get_budget()
    if budget is None:
        return provider.hourly(points, start=start, end=end)
    fetched: dict[LatLon, list] = {}
    for i in range(0, len(points), budget.batch_limit):
        chunk = points[i : i + budget.batch_limit]
        budget.acquire(len(chunk))
        fetched.update(provider.hourly(chunk, start=start, end=end))
    return fetched


def _now() -> float:
    return time.time()
