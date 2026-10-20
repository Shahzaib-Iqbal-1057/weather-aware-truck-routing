from datetime import UTC, datetime

import pytest

from tests.conftest import FakeWeather
from trips.providers.base import ProviderError
from trips.services.weather import weather_at

ETA = datetime(2026, 10, 20, 9, 40, tzinfo=UTC)
LATER = datetime(2026, 10, 20, 13, 5, tzinfo=UTC)


def test_returns_the_forecast_for_the_hour_covering_each_eta():
    provider = FakeWeather()

    [weather] = weather_at([((35.4672, -97.5164), ETA)], provider=provider)

    assert weather.hour == datetime(2026, 10, 20, 10, tzinfo=UTC)


def test_nearby_checkpoints_share_one_lookup_and_the_window_covers_all_etas():
    provider = FakeWeather()
    stops = [((35.4672, -97.5164), ETA), ((35.4669, -97.5170), ETA), ((36.0, -98.0), LATER)]

    results = weather_at(stops, provider=provider)

    assert len(results) == 3
    [call] = provider.calls
    assert sorted(call["points"]) == [(35.45, -97.5), (36.0, -98.0)]
    assert call["start"] == datetime(2026, 10, 20, 10, tzinfo=UTC)
    assert call["end"] == datetime(2026, 10, 20, 14, tzinfo=UTC)


def test_repeated_lookups_are_served_from_cache():
    provider = FakeWeather()
    stops = [((35.4672, -97.5164), ETA)]

    weather_at(stops, provider=provider)
    weather_at(stops, provider=provider)

    assert len(provider.calls) == 1


def test_missing_forecast_hours_come_back_as_unknown():
    class NoData(FakeWeather):
        def hourly(self, points, *, start, end):
            return {point: [] for point in points}

    assert weather_at([((35.45, -97.5), ETA)], provider=NoData()) == [None]


def test_provider_failures_are_raised():
    with pytest.raises(ProviderError):
        weather_at([((35.45, -97.5), ETA)], provider=FakeWeather(error=ProviderError("down")))
