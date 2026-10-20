"""Stage 3: weather at each checkpoint, for the hour the truck is there."""

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

# Forecasts update roughly hourly. Nothing older than this is ever served.
CACHE_SECONDS = 30 * 60


@dataclass(frozen=True)
class _CachedForecast:
    """One fetch for one grid point. Replaced wholesale on refetch, never merged, so every record
    in it is exactly as old as `fetched_at`."""

    fetched_at: float
    start: datetime
    end: datetime
    records: dict[datetime, HourlyWeather]

    def answers(self, hour: datetime, now: float) -> bool:
        """True if this fetch is fresh and covered `hour` (even if the hour had no data)."""
        return now - self.fetched_at < CACHE_SECONDS and self.start <= hour <= self.end


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

    now = _now()
    cached = cache.get_many([_cache_key(point) for point in hours_by_point])
    forecasts: dict[LatLon, _CachedForecast] = {
        point: entry
        for point in hours_by_point
        if (entry := cached.get(_cache_key(point))) is not None
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
                    if point in forecasts and now - forecasts[point].fetched_at < CACHE_SECONDS
                    else ()
                ),
            )
        ]
        start, end = min(spans), max(spans)
        fetched = (provider or get_weather_provider()).hourly(stale, start=start, end=end)
        fresh = {
            point: _CachedForecast(now, start, end, {r.hour: r for r in fetched.get(point, [])})
            for point in stale
        }
        cache.set_many({_cache_key(point): entry for point, entry in fresh.items()}, CACHE_SECONDS)
        forecasts.update(fresh)

    return [forecasts[point].records.get(hour) for point, hour in wanted]


def _now() -> float:
    return time.time()


def _cache_key(point: LatLon) -> str:
    return f"weather:{point[0]:.4f},{point[1]:.4f}"
