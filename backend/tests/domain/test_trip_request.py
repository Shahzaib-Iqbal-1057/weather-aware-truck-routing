from datetime import UTC, datetime

import pytest

from trips.domain import trip_request
from trips.domain.trip_request import TripValidationError, build_trip_request
from trips.domain.types import Place, PlaceKind

DENVER = Place(label="Denver, CO", lat=39.7392, lon=-104.9903, kind=PlaceKind.CITY)
DALLAS = Place(label="Dallas, TX", lat=32.7767, lon=-96.7970, kind=PlaceKind.CITY)
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)  # 06:00 in Denver (MDT, UTC-6)


def build(**overrides):
    values = {
        "origin": DENVER,
        "destination": DALLAS,
        "departure_local": datetime(2026, 10, 20, 8, 0),
        "weight_lb": 40_000,
        "spacing_mi": 25,
        "now": NOW,
    }
    return build_trip_request(**(values | overrides))


def errors_of(**overrides) -> dict[str, str]:
    with pytest.raises(TripValidationError) as exc_info:
        build(**overrides)
    return exc_info.value.errors


def test_departure_is_read_in_the_origin_time_zone():
    trip, warnings = build()

    assert trip.departure_timezone == "America/Denver"
    assert trip.departure_utc == datetime(2026, 10, 20, 14, 0, tzinfo=UTC)
    assert trip.departure_local.strftime("%H:%M %Z") == "08:00 MDT"
    assert warnings == []


def test_departure_uses_standard_time_after_daylight_saving_ends():
    now = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
    trip, _ = build(departure_local=datetime(2026, 11, 11, 8, 0), now=now)

    assert trip.departure_utc == datetime(2026, 11, 11, 15, 0, tzinfo=UTC)  # MST, UTC-7


def test_both_places_get_their_own_time_zone():
    trip, _ = build()

    assert trip.origin.timezone == "America/Denver"
    assert trip.destination.timezone == "America/Chicago"


@pytest.mark.parametrize("weight_lb", [1_000, 30_000, 80_000])
def test_accepts_weights_within_legal_range(weight_lb):
    trip, _ = build(weight_lb=weight_lb)
    assert trip.weight_lb == weight_lb


@pytest.mark.parametrize("weight_lb", [0, 999, 80_001, 150_000])
def test_rejects_weights_outside_legal_range(weight_lb):
    assert "weight_lb" in errors_of(weight_lb=weight_lb)


@pytest.mark.parametrize("spacing_mi", [10, 25, 50])
def test_accepts_supported_spacings(spacing_mi):
    trip, _ = build(spacing_mi=spacing_mi)
    assert trip.spacing_mi == spacing_mi


@pytest.mark.parametrize("spacing_mi", [0, 5, 30, 100])
def test_rejects_unsupported_spacings(spacing_mi):
    assert "spacing_mi" in errors_of(spacing_mi=spacing_mi)


def test_rejects_same_origin_and_destination():
    nearby = Place(label="Denver Civic Center", lat=39.7400, lon=-104.9910)
    assert "destination" in errors_of(destination=nearby)


def test_allows_departure_slightly_in_the_past_for_form_submission_delay():
    _, warnings = build(departure_local=datetime(2026, 10, 19, 5, 50))  # 10 min ago
    assert warnings == []


def test_rejects_departure_in_the_past():
    errors = errors_of(departure_local=datetime(2026, 10, 19, 5, 30))  # 30 min ago
    assert errors["departure_local"] == "Departure time is in the past."


def test_warns_when_departure_is_beyond_reliable_forecast():
    _, warnings = build(departure_local=datetime(2026, 10, 22, 8, 0))  # ~3 days ahead
    assert len(warnings) == 1
    assert "48 hours" in warnings[0]


def test_rejects_departure_more_than_seven_days_ahead():
    errors = errors_of(departure_local=datetime(2026, 10, 27, 8, 0))
    assert errors["departure_local"] == "Departure must be within the next 7 days."


def test_rejects_departure_with_an_offset():
    errors = errors_of(departure_local=datetime(2026, 10, 20, 8, 0, tzinfo=UTC))
    assert "departure_local" in errors


def test_rejects_origin_without_a_time_zone(monkeypatch):
    monkeypatch.setattr(trip_request, "timezone_at", lambda lat, lon: None)
    assert "origin" in errors_of()


def test_reports_every_invalid_field_at_once():
    errors = errors_of(weight_lb=90_000, spacing_mi=30, destination=DENVER)
    assert set(errors) == {"weight_lb", "spacing_mi", "destination"}
