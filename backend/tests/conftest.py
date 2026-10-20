from datetime import timedelta

import pytest
from django.core.cache import cache

from trips.domain.weather import HourlyWeather
from trips.services import weather as weather_service


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class FakeWeather:
    """Calm weather everywhere, every hour. Records each call so tests can inspect them."""

    def __init__(self, error: Exception | None = None, **overrides):
        self.error = error
        self.overrides = overrides
        self.calls: list[dict] = []

    def hourly(self, points, *, start, end):
        self.calls.append({"points": list(points), "start": start, "end": end})
        if self.error:
            raise self.error
        hours = int((end - start).total_seconds() // 3600) + 1
        return {
            point: [self.record(start + timedelta(hours=h)) for h in range(hours)]
            for point in points
        }

    def record(self, hour):
        values = {
            "wind_mph": 8.0,
            "gust_mph": 15.0,
            "rain_in_per_hr": 0.0,
            "snow_in_per_hr": 0.0,
            "temperature_f": 60.0,
            "weather_code": 0,
        } | self.overrides
        return HourlyWeather(hour=hour, **values)


@pytest.fixture(autouse=True)
def fake_weather(monkeypatch):
    """No test talks to the real weather service."""
    fake = FakeWeather()
    monkeypatch.setattr(weather_service, "get_weather_provider", lambda: fake)
    return fake
