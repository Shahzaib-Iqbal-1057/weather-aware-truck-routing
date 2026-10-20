from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from tests.conftest import FakeWeather
from tests.factories import make_route, path
from trips.providers.base import NoRouteError, ProviderError
from trips.services import plan_trip
from trips.services import weather as weather_service

DENVER = {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903, "kind": "city"}
DALLAS = {"label": "Dallas, TX", "lat": 32.7767, "lon": -96.7970, "kind": "city"}


FAST = make_route(path((39.74, -104.99), (32.78, -96.80)), hours=12)
NORTH = make_route(path((39.74, -104.99), (37.7, -97.3), (32.78, -96.80)), hours=12.5)
SOUTH = make_route(path((39.74, -104.99), (35.2, -101.8), (32.78, -96.80)), hours=13)


class FakeRouter:
    def __init__(self, result):
        self.result = result

    def routes(self, *args, **kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def fake_router(monkeypatch):
    def use(result):
        monkeypatch.setattr(plan_trip, "get_router", lambda: FakeRouter(result))

    use([SOUTH, FAST, NORTH])
    return use


def denver_wall_clock(hours_from_now: float) -> str:
    moment = timezone.now() + timedelta(hours=hours_from_now)
    return moment.astimezone(ZoneInfo("America/Denver")).strftime("%Y-%m-%dT%H:%M")


def post(**overrides):
    payload = {
        "origin": DENVER,
        "destination": DALLAS,
        "departure_local": denver_wall_clock(2),
        "cargo_weight_lb": 30_000,
        "spacing_mi": 10,
    } | overrides
    return APIClient().post(reverse("trip-plan"), payload, format="json")


def test_returns_normalized_trip():
    departure = denver_wall_clock(2)

    response = post(departure_local=departure)

    assert response.status_code == 200
    body = response.json()
    trip = body["trip"]
    assert trip["departure_local"] == departure
    assert trip["departure_timezone"] == "America/Denver"
    assert trip["departure_timezone_abbr"] in {"MDT", "MST"}
    assert trip["departure_utc"].endswith("Z")
    assert trip["origin"]["timezone"] == "America/Denver"
    assert trip["destination"]["timezone"] == "America/Chicago"
    assert body["warnings"] == []


def test_spacing_defaults_to_10_miles():
    payload = {
        "origin": DENVER,
        "destination": DALLAS,
        "departure_local": denver_wall_clock(2),
        "cargo_weight_lb": 30_000,
    }

    response = APIClient().post(reverse("trip-plan"), payload, format="json")

    assert response.json()["trip"]["spacing_mi"] == 10


def test_returns_warning_for_departure_beyond_48_hours():
    response = post(departure_local=denver_wall_clock(72))

    assert response.status_code == 200
    assert len(response.json()["warnings"]) == 1


def test_returns_field_errors_for_rule_violations():
    response = post(cargo_weight_lb=90_000, destination=DENVER)

    assert response.status_code == 400
    assert set(response.json()) == {"cargo_weight_lb", "destination"}


def test_rejects_malformed_input():
    response = post(departure_local="tomorrow", origin={"label": "x", "lat": 200, "lon": 0})

    assert response.status_code == 400
    body = response.json()
    assert "departure_local" in body
    assert "lat" in body["origin"]


def test_returns_routes_labelled_by_travel_time():
    response = post()

    assert response.status_code == 200
    routes = response.json()["routes"]
    assert [r["id"] for r in routes] == ["A", "B", "C"]
    assert [r["driving_time_s"] for r in routes] == [12 * 3600, 12.5 * 3600, 13 * 3600]
    first = routes[0]
    assert first["distance_mi"] == pytest.approx(FAST.length_m / 1609.344, abs=0.1)
    # Display geometry is [lon, lat] and simplified (a straight line needs only its ends).
    assert first["geometry"] == [[-104.99, 39.74], [-96.8, 32.78]]
    # Each route is labelled on its own road, away from the others.
    assert [r["label_position"] for r in routes] != [routes[0]["label_position"]] * 3
    assert all(len(r["label_position"]) == 2 for r in routes)
    assert response.json()["notes"] == []


def test_no_route_returns_422(fake_router):
    fake_router(NoRouteError("ocean"))

    response = post()

    assert response.status_code == 422
    assert response.json() == {"detail": "No truck route exists between these places."}


def test_routing_failure_returns_502(fake_router):
    fake_router(ProviderError("down"))

    response = post()

    assert response.status_code == 502
    assert response.json() == {"detail": "Route planning is temporarily unavailable."}


def test_routes_include_checkpoints_rest_stops_and_arrival():
    departure = denver_wall_clock(2)

    route = post(departure_local=departure).json()["routes"][0]  # 12 h of driving

    # 12 h of driving: 30-min break at 8 h, 10-h rest at 11 h.
    assert [stop["kind"] for stop in route["rest_stops"]] == ["break", "rest"]
    assert route["trip_time_s"] == 12 * 3600 + 30 * 60 + 10 * 3600
    first, second = route["checkpoints"][0], route["checkpoints"][1]
    assert first["mile"] == 0
    assert second["mile"] == 10
    assert first["eta_utc"].endswith("Z")
    assert route["checkpoints"][-1]["eta_utc"] == route["arrival_utc"]
    stop = route["rest_stops"][1]
    assert set(stop) == {"kind", "position", "mile", "starts_utc", "ends_utc"}


def test_checkpoints_include_weather_for_their_hour():
    body = post().json()

    assert body["weather_available"] is True
    weather = body["routes"][0]["checkpoints"][1]["weather"]
    assert weather == {
        "forecast_hour_utc": weather["forecast_hour_utc"],
        "wind_mph": 8.0,
        "gust_mph": 15.0,
        "rain_in_per_hr": 0.0,
        "snow_in_per_hr": 0.0,
        "temperature_f": 60,
        "conditions": "Clear",
    }


def test_weather_outage_still_returns_routes(monkeypatch):
    failing = FakeWeather(error=ProviderError("down"))
    monkeypatch.setattr(weather_service, "get_weather_provider", lambda: failing)

    response = post()

    assert response.status_code == 200
    body = response.json()
    assert body["weather_available"] is False
    assert len(body["routes"]) == 3
    assert body["routes"][0]["checkpoints"][0]["weather"] is None
    assert any("Weather is unavailable" in note for note in body["notes"])


def test_checkpoints_include_risk_level_and_reasons(monkeypatch):
    stormy = FakeWeather(wind_mph=20.0, gust_mph=57.3, rain_in_per_hr=0.31)
    monkeypatch.setattr(weather_service, "get_weather_provider", lambda: stormy)

    checkpoint = post().json()["routes"][0]["checkpoints"][0]

    assert checkpoint["risk"] == {"level": "high", "reasons": ["Gusts 57.3 mph", "Rain 0.31 in/hr"]}
    assert checkpoint["weather"]["gust_mph"] == 57.3


def test_risk_is_unknown_without_weather(monkeypatch):
    failing = FakeWeather(error=ProviderError("down"))
    monkeypatch.setattr(weather_service, "get_weather_provider", lambda: failing)

    checkpoint = post().json()["routes"][0]["checkpoints"][0]

    assert checkpoint["risk"]["level"] == "unknown"


def test_routes_include_totals_and_the_plan_names_a_recommended_route():
    body = post().json()

    assert body["routes"][0]["totals"] == {
        "severe_mi": 0.0,
        "high_mi": 0.0,
        "no_travel_mi": 0.0,
        "unknown_mi": 0.0,
        "average_risk": 0.0,
    }
    assert body["recommendation"]["route_id"] == "A"
    assert body["recommendation"]["reason"].startswith("Route A:")


def test_no_recommendation_without_weather(monkeypatch):
    failing = FakeWeather(error=ProviderError("down"))
    monkeypatch.setattr(weather_service, "get_weather_provider", lambda: failing)

    body = post().json()

    assert body["recommendation"]["route_id"] is None
    assert body["routes"][0]["totals"]["average_risk"] is None
