"""Stage 3: weather at each checkpoint, for the hour the truck is there."""

from datetime import datetime

from django.conf import settings
from django.core.cache import cache

from trips.domain.geo import LatLon
from trips.domain.weather import HourlyWeather, forecast_hour, grid_point
from trips.providers.base import WeatherProvider
from trips.providers.open_meteo import OpenMeteoWeather

# Forecasts update roughly hourly; re-planning within this window reuses what we fetched.
CACHE_SECONDS = 30 * 60


def get_weather_provider() -> WeatherProvider:
    return OpenMeteoWeather(settings.OPEN_METEO_API_KEY)


def weather_at(
    stops: list[tuple[LatLon, datetime]], *, provider: WeatherProvider | None = None
) -> list[HourlyWeather | None]:
    """Forecast for each (position, ETA), in order. None where the forecast has no data.

    Positions are snapped to the weather grid, so nearby checkpoints (e.g. on road shared by two
    routes) share one lookup. Each grid point's hourly forecast is cached as one entry. Raises
    ProviderError if the weather service fails.
    """
    wanted = [(grid_point(position), forecast_hour(eta)) for position, eta in stops]
    points = {point for point, _ in wanted}
    cached = cache.get_many([_cache_key(point) for point in points])
    series: dict[LatLon, dict[datetime, HourlyWeather]] = {
        point: cached.get(_cache_key(point), {}) for point in points
    }

    missing = [(point, hour) for point, hour in set(wanted) if hour not in series[point]]
    if missing:
        hours = [hour for _, hour in missing]
        forecasts = (provider or get_weather_provider()).hourly(
            sorted({point for point, _ in missing}), start=min(hours), end=max(hours)
        )
        for point, records in forecasts.items():
            series[point] = series[point] | {record.hour: record for record in records}
        cache.set_many({_cache_key(point): series[point] for point in forecasts}, CACHE_SECONDS)

    return [series[point].get(hour) for point, hour in wanted]


def _cache_key(point: LatLon) -> str:
    return f"weather:{point[0]:.4f},{point[1]:.4f}"
