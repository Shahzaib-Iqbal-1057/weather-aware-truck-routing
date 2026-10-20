"""Hourly forecasts from Open-Meteo (https://open-meteo.com).

Free and keyless by default. With a paid-plan key, requests go to the customer endpoint, which
has no per-minute/hour/day limits.
"""

from datetime import UTC, datetime
from typing import Any

import requests

from trips.domain.geo import LatLon
from trips.domain.weather import HourlyWeather
from trips.providers.base import ProviderError

FREE_URL = "https://api.open-meteo.com/v1/forecast"
PAID_URL = "https://customer-api.open-meteo.com/v1/forecast"
# Locations per request. Keeps URLs short; a long trip needs only a few requests.
BATCH_SIZE = 100
VARIABLES = (
    "wind_speed_10m",
    "wind_gusts_10m",
    "rain",
    "showers",
    "snowfall",
    "temperature_2m",
    "weather_code",
)


class OpenMeteoWeather:
    def __init__(
        self, api_key: str = "", *, session: requests.Session | None = None, timeout: float = 20
    ):
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout

    def hourly(
        self, points: list[LatLon], *, start: datetime, end: datetime
    ) -> dict[LatLon, list[HourlyWeather]]:
        forecasts: dict[LatLon, list[HourlyWeather]] = {}
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            results = self._fetch(batch, start, end)
            forecasts.update(zip(batch, (parse_hourly(r) for r in results), strict=True))
        return forecasts

    def _fetch(self, points: list[LatLon], start: datetime, end: datetime) -> list[dict[str, Any]]:
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat, _ in points),
            "longitude": ",".join(f"{lon:.4f}" for _, lon in points),
            "hourly": ",".join(VARIABLES),
            "start_hour": _hour_param(start),
            "end_hour": _hour_param(end),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "temperature_unit": "fahrenheit",
            "timeformat": "unixtime",
            "timezone": "GMT",
        }
        url = FREE_URL
        if self._api_key:
            url, params["apikey"] = PAID_URL, self._api_key

        try:
            response = self._session.get(url, params=params, timeout=self._timeout)
        except requests.RequestException as exc:
            raise ProviderError(f"Open-Meteo request failed: {type(exc).__name__}") from None
        if response.status_code == 429:
            raise ProviderError("Open-Meteo rate limit reached.")
        if response.status_code != 200:
            raise ProviderError(f"Open-Meteo failed with HTTP {response.status_code}.")

        payload = response.json()
        # One location comes back as an object, several as a list.
        results = payload if isinstance(payload, list) else [payload]
        if len(results) != len(points):
            raise ProviderError("Open-Meteo returned a different number of locations.")
        return results


def _hour_param(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:00")


def parse_hourly(result: dict[str, Any]) -> list[HourlyWeather]:
    """Hours with any risk value missing are left out, so they read as "unknown", never as calm."""
    hourly = result["hourly"]
    records = []
    for i, timestamp in enumerate(hourly["time"]):
        wind, gust = hourly["wind_speed_10m"][i], hourly["wind_gusts_10m"][i]
        rain, showers, snow = hourly["rain"][i], hourly["showers"][i], hourly["snowfall"][i]
        if None in (wind, rain, showers, snow):
            continue
        code = hourly["weather_code"][i]
        records.append(
            HourlyWeather(
                hour=datetime.fromtimestamp(timestamp, tz=UTC),
                wind_mph=float(wind),
                gust_mph=float(gust) if gust is not None else None,
                rain_in_per_hr=float(rain) + float(showers),
                snow_in_per_hr=float(snow),
                temperature_f=hourly["temperature_2m"][i],
                weather_code=int(code) if code is not None else None,
            )
        )
    return records
