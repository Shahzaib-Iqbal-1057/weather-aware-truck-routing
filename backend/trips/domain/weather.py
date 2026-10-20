"""Stage 3: forecast weather at a checkpoint, for the hour the truck is there."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from trips.domain.geo import LatLon

# Checkpoints are snapped to a ~5 km grid before asking for weather. The finest US forecast model
# works in ~3 km squares (coarser models 13–25 km), so this loses nothing, and checkpoints of
# different routes on the same road share one lookup.
WEATHER_GRID_DEG = 0.05


@dataclass(frozen=True)
class HourlyWeather:
    """Forecast for one hour at one place, in the risk table's units.

    Rain and snow are totals for the hour, i.e. intensity in inches per hour. Rain includes
    showers: the provider reports steady rain and convective showers separately, and both fall
    on the road.
    """

    hour: datetime  # end of the forecast hour (UTC); rain/snow cover the hour before it
    wind_mph: float  # sustained wind at 10 m, used by the risk rules
    gust_mph: float | None  # shown, and 55+ mph raises the wind level to at least High
    rain_in_per_hr: float
    snow_in_per_hr: float
    temperature_f: float | None
    weather_code: int | None  # WMO code


def grid_point(point: LatLon) -> LatLon:
    lat, lon = point
    return (
        round(round(lat / WEATHER_GRID_DEG) * WEATHER_GRID_DEG, 4),
        round(round(lon / WEATHER_GRID_DEG) * WEATHER_GRID_DEG, 4),
    )


def forecast_hour(eta: datetime) -> datetime:
    """The hourly record covering `eta`: the next full hour (UTC), since each record holds the
    hour before it. A truck at 9:40 is in the 9:00–10:00 hour, which is the 10:00 record."""
    hour = eta.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return hour if hour == eta else hour + timedelta(hours=1)


# WMO weather interpretation codes, as used by Open-Meteo.
_CONDITIONS = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Violent showers",
    85: "Light snow showers",
    86: "Snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Thunderstorm with heavy hail",
}


def describe_conditions(weather_code: int | None) -> str | None:
    return _CONDITIONS.get(weather_code) if weather_code is not None else None
