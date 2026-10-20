from datetime import UTC, datetime

import pytest

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
        "cargo_weight_lb": 30_000,
        "spacing_mi": 10,
        "origin_timezone": "America/Denver",
        "destination_timezone": "America/Chicago",
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


def test_both_places_carry_their_time_zone():
    trip, _ = build()

    assert trip.origin.timezone == "America/Denver"
    assert trip.destination.timezone == "America/Chicago"


@pytest.mark.parametrize("cargo", [0, 30_000, 45_000])
def test_accepts_cargo_from_empty_to_the_legal_maximum(cargo):
    trip, _ = build(cargo_weight_lb=cargo)
    assert trip.cargo_weight_lb == cargo


@pytest.mark.parametrize("cargo", [-1, 45_001, 80_000])
def test_rejects_cargo_outside_the_legal_range(cargo):
    assert "cargo_weight_lb" in errors_of(cargo_weight_lb=cargo)


@pytest.mark.parametrize("spacing_mi", [10, 25, 50])
def test_accepts_supported_spacings(spacing_mi):
    trip, _ = build(spacing_mi=spacing_mi)
    assert trip.spacing_mi == spacing_mi


@pytest.mark.parametrize("spacing_mi", [0, 5, 30, 100])
def test_rejects_unsupported_spacings(spacing_mi):
    assert "spacing_mi" in errors_of(spacing_mi=spacing_mi)


def test_rejects_places_outside_the_us():
    paris = Place(label="Paris", lat=48.86, lon=2.35)
    assert errors_of(origin=paris, origin_timezone="Europe/Paris")["origin"] == (
        "Only places in the United States are supported."
    )


@pytest.mark.parametrize(
    ("lat", "lon"), [(61.22, -149.90), (21.31, -157.86), (25.76, -80.19), (48.75, -122.48)]
)
def test_accepts_alaska_hawaii_and_the_edges_of_the_lower_48(lat, lon):
    build(destination=Place(label="Somewhere, US", lat=lat, lon=lon))


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


def test_rejects_origin_without_a_time_zone():
    assert "origin" in errors_of(origin_timezone=None)


def test_rejects_a_departure_in_the_daylight_saving_gap():
    # On 8 Mar 2026 Denver clocks jump from 2:00 to 3:00, so 2:30 never happens.
    now = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    errors = errors_of(departure_local=datetime(2026, 3, 8, 2, 30), now=now)
    assert "daylight saving" in errors["departure_local"]


def test_accepts_the_repeated_hour_when_clocks_fall_back_as_its_first_occurrence():
    # On 1 Nov 2026 Denver's 1:30 happens twice; the first (daylight time, UTC-6) is used.
    now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
    trip, _ = build(departure_local=datetime(2026, 11, 1, 1, 30), now=now)
    assert trip.departure_utc == datetime(2026, 11, 1, 7, 30, tzinfo=UTC)


def test_reports_every_invalid_field_at_once():
    errors = errors_of(cargo_weight_lb=90_000, spacing_mi=30, destination=DENVER)
    assert set(errors) == {"cargo_weight_lb", "spacing_mi", "destination"}
