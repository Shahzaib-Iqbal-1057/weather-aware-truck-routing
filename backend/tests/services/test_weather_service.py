from dataclasses import replace
from datetime import UTC, datetime

import pytest

from tests.conftest import FakeWeather
from trips.providers.base import ProviderError
from trips.services import weather as weather_service
from trips.services.weather import CACHE_SECONDS, weather_at

ETA = datetime(2026, 10, 20, 9, 40, tzinfo=UTC)
LATER = datetime(2026, 10, 20, 13, 5, tzinfo=UTC)


def test_returns_the_forecast_for_the_hour_covering_each_eta():
    provider = FakeWeather()

    [weather] = weather_at([((35.4672, -97.5164), ETA)], provider=provider)

    assert weather.hour == datetime(2026, 10, 20, 10, tzinfo=UTC)


def test_nearby_checkpoints_share_one_lookup_and_the_window_covers_all_etas():
    provider = FakeWeather()
    checkpoint_times = [
        ((35.4672, -97.5164), ETA),
        ((35.4669, -97.5170), ETA),
        ((36.0, -98.0), LATER),
    ]

    results = weather_at(checkpoint_times, provider=provider)

    assert len(results) == 3
    [call] = provider.calls
    assert sorted(call["points"]) == [(35.45, -97.5), (36.0, -98.0)]
    assert call["start"] == datetime(2026, 10, 20, 10, tzinfo=UTC)
    assert call["end"] == datetime(2026, 10, 20, 14, tzinfo=UTC)


def test_repeated_lookups_are_served_from_cache():
    provider = FakeWeather()
    checkpoint_times = [((35.4672, -97.5164), ETA)]

    weather_at(checkpoint_times, provider=provider)
    weather_at(checkpoint_times, provider=provider)

    assert len(provider.calls) == 1


def test_missing_forecast_hours_come_back_as_unknown():
    class NoData(FakeWeather):
        def hourly(self, points, *, start, end):
            return {point: [] for point in points}

    assert weather_at([((35.45, -97.5), ETA)], provider=NoData()) == [None]


def test_provider_failures_are_raised():
    with pytest.raises(ProviderError):
        weather_at([((35.45, -97.5), ETA)], provider=FakeWeather(error=ProviderError("down")))


class ChangingWeather(FakeWeather):
    """Wind goes up by 10 mph on every fetch, so stale answers are easy to spot."""

    def record(self, hour):
        return replace(super().record(hour), wind_mph=10.0 * len(self.calls))


def test_cached_forecasts_expire_even_when_later_trips_add_new_hours(monkeypatch):
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(weather_service, "_now", lambda: clock["now"])
    provider = ChangingWeather()
    point = (35.45, -97.5)

    [first] = weather_at([(point, ETA)], provider=provider)  # fetch 1: 10 mph
    clock["now"] += 20 * 60
    weather_at([(point, LATER)], provider=provider)  # needs a new hour: fetch 2
    clock["now"] += 15 * 60  # 35 min after fetch 1, 15 min after fetch 2
    [again] = weather_at([(point, ETA)], provider=provider)

    assert first.wind_mph == 10.0
    # Fetch 2 replaced fetch 1 (re-covering 9:40), so the answer is 15 min old, not 35.
    assert again.wind_mph == 20.0
    clock["now"] += CACHE_SECONDS
    [expired] = weather_at([(point, ETA)], provider=provider)
    assert expired.wind_mph == 30.0


def test_hours_already_fetched_without_data_are_not_fetched_again():
    class NoData(FakeWeather):
        def hourly(self, points, *, start, end):
            super().hourly(points, start=start, end=end)
            return {point: [] for point in points}

    provider = NoData()
    weather_at([((35.45, -97.5), ETA)], provider=provider)
    weather_at([((35.45, -97.5), ETA)], provider=provider)

    assert len(provider.calls) == 1
