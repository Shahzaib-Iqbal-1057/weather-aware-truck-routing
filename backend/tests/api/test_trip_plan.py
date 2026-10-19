from datetime import timedelta
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

DENVER = {"label": "Denver, CO", "lat": 39.7392, "lon": -104.9903, "kind": "city"}
DALLAS = {"label": "Dallas, TX", "lat": 32.7767, "lon": -96.7970, "kind": "city"}


def denver_wall_clock(hours_from_now: float) -> str:
    moment = timezone.now() + timedelta(hours=hours_from_now)
    return moment.astimezone(ZoneInfo("America/Denver")).strftime("%Y-%m-%dT%H:%M")


def post(**overrides):
    payload = {
        "origin": DENVER,
        "destination": DALLAS,
        "departure_local": denver_wall_clock(2),
        "weight_lb": 40_000,
        "spacing_mi": 25,
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


def test_spacing_defaults_to_25_miles():
    payload = {
        "origin": DENVER,
        "destination": DALLAS,
        "departure_local": denver_wall_clock(2),
        "weight_lb": 40_000,
    }

    response = APIClient().post(reverse("trip-plan"), payload, format="json")

    assert response.json()["trip"]["spacing_mi"] == 25


def test_returns_warning_for_departure_beyond_48_hours():
    response = post(departure_local=denver_wall_clock(72))

    assert response.status_code == 200
    assert len(response.json()["warnings"]) == 1


def test_returns_field_errors_for_rule_violations():
    response = post(weight_lb=90_000, destination=DENVER)

    assert response.status_code == 400
    assert set(response.json()) == {"weight_lb", "destination"}


def test_rejects_malformed_input():
    response = post(departure_local="tomorrow", origin={"label": "x", "lat": 200, "lon": 0})

    assert response.status_code == 400
    body = response.json()
    assert "departure_local" in body
    assert "lat" in body["origin"]
