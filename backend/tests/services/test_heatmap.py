from datetime import timedelta

import pytest
from django.utils import timezone

from tests.conftest import FakeWeather
from tests.factories import make_route, path
from trips.domain.risk import RiskLevel
from trips.domain.trip_request import TripRequest
from trips.domain.types import Place
from trips.services import heatmap as heatmap_service
from trips.services.heatmap import HOURS, build_heatmap

START, END = (35.0, -100.0), (35.0, -98.0)
ROUTE = make_route(path(START, END, steps_per_leg=400), hours=3)


class FakeRouter:
    def routes(self, *args, **kwargs):
        return [ROUTE]


def make_trip(cargo=30_000):
    return TripRequest(
        origin=Place(label="Origin", lat=START[0], lon=START[1]),
        destination=Place(label="Destination", lat=END[0], lon=END[1]),
        departure_utc=timezone.now() + timedelta(hours=2),
        departure_timezone="America/Chicago",
        cargo_weight_lb=cargo,
        spacing_mi=10,
    )


def test_every_cell_has_48_hourly_levels_from_the_departure_hour():
    weather = FakeWeather()

    heatmap = build_heatmap(make_trip(), router=FakeRouter(), weather=weather)

    assert heatmap.cells
    assert all(len(cell.levels) == HOURS for cell in heatmap.cells)
    assert weather.calls[0]["start"] == heatmap.start
    assert weather.calls[0]["end"] == heatmap.start + timedelta(hours=HOURS - 1)
    assert all(level == RiskLevel.LOW for cell in heatmap.cells for level in cell.levels)


@pytest.mark.parametrize(
    ("cargo", "expected"), [(30_000, RiskLevel.SEVERE), (30_001, RiskLevel.NO_TRAVEL)]
)
def test_levels_use_the_trips_cargo(cargo, expected):
    windy = FakeWeather(wind_mph=47.0)

    heatmap = build_heatmap(make_trip(cargo), router=FakeRouter(), weather=windy)

    assert heatmap.cells[0].levels[0] == expected


def test_repeated_maps_come_from_the_cache():
    weather, trip = FakeWeather(), make_trip()
    build_heatmap(trip, router=FakeRouter(), weather=weather)
    build_heatmap(trip, router=FakeRouter(), weather=weather)
    assert len(weather.calls) == 1


def test_a_low_daily_allowance_uses_fewer_cells(monkeypatch, settings):
    settings.HEATMAP_MAX_CELLS = 40
    full = build_heatmap(make_trip(), router=FakeRouter(), weather=FakeWeather())

    class NearlyUsedUp:
        batch_limit = 550

        def remaining_today(self):
            return 100

        def acquire(self, n):
            pass

    monkeypatch.setattr(heatmap_service, "get_budget", lambda: NearlyUsedUp())
    reduced = build_heatmap(make_trip(), router=FakeRouter(), weather=FakeWeather())

    assert len(reduced.cells) < len(full.cells)
    assert reduced.cell_deg > full.cell_deg
