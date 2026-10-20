from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from tests.conftest import FakeWeather
from tests.factories import make_route, path
from trips.domain.trip_request import TripRequest
from trips.domain.types import Place
from trips.providers.base import NoRouteError, ProviderError
from trips.services.plan_trip import plan_trip

START, END = (35.0, -100.0), (35.0, -96.0)
DIRECT = make_route(path(START, END), hours=4)
NORTH = make_route(path(START, (36.0, -98.0), END), hours=4.5)
SOUTH = make_route(path(START, (34.0, -98.0), END), hours=4.6)
DIRECT_COPY = make_route([(lat + 0.001, lon) for lat, lon in DIRECT.points], hours=4.05)


class FakeRouter:
    """Returns scripted responses in order and records each call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def routes(self, origin, destination, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def routes_of(plan):
    return [planned.route for planned in plan.routes]


def make_trip(departure_utc: datetime | None = None) -> TripRequest:
    return TripRequest(
        origin=Place(label="Origin", lat=START[0], lon=START[1]),
        destination=Place(label="Destination", lat=END[0], lon=END[1]),
        departure_utc=departure_utc or timezone.now() + timedelta(hours=2),
        departure_timezone="America/Chicago",
        cargo_weight_lb=30_000,
        spacing_mi=10,
    )


def test_uses_the_first_response_when_it_has_three_distinct_routes():
    router = FakeRouter([SOUTH, DIRECT, NORTH, DIRECT_COPY])

    plan = plan_trip(make_trip(), router=router)

    assert routes_of(plan) == [DIRECT, NORTH, SOUTH]
    assert plan.notes == []
    assert len(router.calls) == 1
    assert router.calls[0]["max_alternatives"] == 3
    assert router.calls[0]["avoid_areas"] is None


def test_asks_for_detours_when_too_few_distinct_routes():
    router = FakeRouter([DIRECT, DIRECT_COPY], [NORTH], [SOUTH])

    plan = plan_trip(make_trip(), router=router)

    assert routes_of(plan) == [DIRECT, NORTH, SOUTH]
    assert len(router.calls) == 3
    first_detour, second_detour = router.calls[1], router.calls[2]
    assert first_detour["max_alternatives"] == 0
    assert len(first_detour["avoid_areas"]) == 1  # middle of the one chosen route
    assert first_detour["avoid_areas"][0].contains((35.0, -98.0))
    assert len(second_detour["avoid_areas"]) == 4  # thirds of both chosen routes


def test_keeps_going_when_a_detour_is_impossible_and_notes_the_shortfall():
    router = FakeRouter([DIRECT], NoRouteError("blocked"), [DIRECT_COPY])

    plan = plan_trip(make_trip(), router=router)

    assert routes_of(plan) == [DIRECT]
    assert plan.notes == [
        "Only 1 distinct truck route for this trip: the other options mostly use the same roads."
    ]


def test_no_route_at_all_is_raised():
    with pytest.raises(NoRouteError):
        plan_trip(make_trip(), router=FakeRouter(NoRouteError("ocean")))


def test_repeated_trips_are_served_from_cache():
    router = FakeRouter([DIRECT, NORTH, SOUTH])
    trip = make_trip()

    plan_trip(trip, router=router)
    plan_trip(trip, router=router)

    assert len(router.calls) == 1


def test_departure_in_the_recent_past_is_sent_as_now():
    router = FakeRouter([DIRECT, NORTH, SOUTH])

    plan_trip(make_trip(departure_utc=timezone.now() - timedelta(minutes=5)), router=router)

    assert router.calls[0]["depart_at"] > datetime.now(UTC)


def test_sends_a_standard_semi_with_cargo_plus_the_empty_truck_weight():
    router = FakeRouter([DIRECT, NORTH, SOUTH])

    plan_trip(make_trip(), router=router)  # 30,000 lb cargo

    vehicle = router.calls[0]["vehicle"]
    assert round(vehicle.weight_kg) == 29_484  # 65,000 lb gross
    assert vehicle.height_m == 4.12


def test_each_route_gets_checkpoints_from_the_trip_departure():
    trip = make_trip()
    plan = plan_trip(trip, router=FakeRouter([DIRECT, NORTH, SOUTH]))

    timeline = plan.routes[0].timeline
    assert timeline.checkpoints[0].eta == trip.departure_utc
    assert timeline.checkpoints[1].mile == 10
    assert timeline.arrival == trip.departure_utc + timedelta(hours=4)


def test_every_checkpoint_gets_the_forecast_for_its_eta():
    plan = plan_trip(make_trip(), router=FakeRouter([DIRECT, NORTH, SOUTH]))

    assert plan.weather_available
    for planned in plan.routes:
        assert len(planned.weather) == len(planned.timeline.checkpoints)
        for checkpoint, weather in zip(planned.timeline.checkpoints, planned.weather, strict=True):
            assert weather.hour - timedelta(hours=1) < checkpoint.eta <= weather.hour


def test_routes_are_still_returned_when_weather_fails():
    plan = plan_trip(
        make_trip(),
        router=FakeRouter([DIRECT, NORTH, SOUTH]),
        weather=FakeWeather(error=ProviderError("down")),
    )

    assert routes_of(plan) == [DIRECT, NORTH, SOUTH]
    assert not plan.weather_available
    assert all(w is None for planned in plan.routes for w in planned.weather)
    assert any("Weather is unavailable" in note for note in plan.notes)


def test_a_failed_detour_request_keeps_the_routes_already_found():
    router = FakeRouter([DIRECT, NORTH], ProviderError("HTTP 429"))

    plan = plan_trip(make_trip(), router=router)

    assert routes_of(plan) == [DIRECT, NORTH]
    assert plan.notes[0] == (
        "Only 2 distinct truck routes for this trip: "
        "the search for more routes failed, please try again shortly."
    )


def test_a_failed_detour_is_not_cached_so_the_next_plan_tries_again():
    trip = make_trip()
    plan_trip(trip, router=FakeRouter([DIRECT, NORTH], ProviderError("HTTP 429")))

    plan = plan_trip(trip, router=FakeRouter([DIRECT, NORTH], [SOUTH]))

    assert routes_of(plan) == [DIRECT, NORTH, SOUTH]


def test_each_checkpoint_gets_a_risk_level_from_its_rounded_weather():
    windy = FakeWeather(
        wind_mph=47.04, gust_mph=60.0
    )  # Severe wind; cargo 30,000 lb is not "> 30,000"

    plan = plan_trip(make_trip(), router=FakeRouter([DIRECT, NORTH, SOUTH]), weather=windy)

    first = plan.routes[0]
    assert first.weather[0].wind_mph == 47.0  # rounded once
    assert first.risk[0].level.label == "Severe"
    assert len(first.risk) == len(first.timeline.checkpoints)


def test_risk_is_unknown_when_weather_is_unavailable():
    plan = plan_trip(
        make_trip(),
        router=FakeRouter([DIRECT, NORTH, SOUTH]),
        weather=FakeWeather(error=ProviderError("down")),
    )
    assert all(risk is None for planned in plan.routes for risk in planned.risk)


def test_the_note_says_when_other_routes_were_too_slow():
    too_slow = make_route(path(START, (37.5, -98.0), END), hours=5.5)  # +37%
    plan = plan_trip(make_trip(), router=FakeRouter([DIRECT, too_slow], [], []))

    assert plan.notes == [
        "Only 1 distinct truck route for this trip: the other options are more than 25% slower."
    ]


def test_the_reason_survives_the_route_cache():
    too_slow = make_route(path(START, (37.5, -98.0), END), hours=5.5)
    trip = make_trip()
    plan_trip(trip, router=FakeRouter([DIRECT, too_slow], [], []))

    plan = plan_trip(trip, router=FakeRouter())  # served from cache

    assert "more than 25% slower" in plan.notes[0]
