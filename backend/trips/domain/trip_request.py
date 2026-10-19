"""Stage 0: turn raw form input into a validated TripRequest.

All business rules for the input live here, so the API layer only parses types.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from trips.domain.geo import haversine_miles
from trips.domain.timezones import timezone_at
from trips.domain.types import Place

WEIGHT_MIN_LB = 1_000
WEIGHT_MAX_LB = 80_000  # US federal limit without an overweight permit
SPACING_OPTIONS_MI = (10, 25, 50)
DEFAULT_SPACING_MI = 25
MIN_TRIP_MILES = 1.0

MAX_DEPARTURE_AHEAD = timedelta(days=7)
RELIABLE_FORECAST_HORIZON = timedelta(hours=48)
PAST_DEPARTURE_GRACE = timedelta(minutes=15)


@dataclass(frozen=True)
class TripRequest:
    origin: Place
    destination: Place
    departure_utc: datetime
    departure_timezone: str
    weight_lb: int
    spacing_mi: int

    @property
    def departure_local(self) -> datetime:
        return self.departure_utc.astimezone(ZoneInfo(self.departure_timezone))


class TripValidationError(Exception):
    def __init__(self, errors: dict[str, str]):
        super().__init__(errors)
        self.errors = errors


def build_trip_request(
    *,
    origin: Place,
    destination: Place,
    departure_local: datetime,
    weight_lb: int,
    spacing_mi: int,
    now: datetime,
) -> tuple[TripRequest, list[str]]:
    """Validate the input and return the trip plus any non-blocking warnings.

    `departure_local` is a naive wall-clock time in the origin's time zone.
    Raises TripValidationError with one message per invalid field.
    """
    errors: dict[str, str] = {}

    origin_tz = timezone_at(origin.lat, origin.lon)
    if origin_tz is None:
        errors["origin"] = "Could not determine the time zone for this origin."
    destination_tz = timezone_at(destination.lat, destination.lon)

    if haversine_miles(origin.lat, origin.lon, destination.lat, destination.lon) < MIN_TRIP_MILES:
        errors["destination"] = "Destination must be a different place from the origin."

    if not WEIGHT_MIN_LB <= weight_lb <= WEIGHT_MAX_LB:
        errors["weight_lb"] = f"Weight must be between {WEIGHT_MIN_LB:,} and {WEIGHT_MAX_LB:,} lb."

    if spacing_mi not in SPACING_OPTIONS_MI:
        options = ", ".join(str(option) for option in SPACING_OPTIONS_MI)
        errors["spacing_mi"] = f"Checkpoint spacing must be one of {options} miles."

    warnings: list[str] = []
    departure_utc = None
    if departure_local.tzinfo is not None:
        errors["departure_local"] = "Departure time must not include a time zone offset."
    elif origin_tz is not None:
        departure_utc = departure_local.replace(tzinfo=ZoneInfo(origin_tz)).astimezone(UTC)
        if departure_utc < now - PAST_DEPARTURE_GRACE:
            errors["departure_local"] = "Departure time is in the past."
        elif departure_utc > now + MAX_DEPARTURE_AHEAD:
            errors["departure_local"] = "Departure must be within the next 7 days."
        elif departure_utc > now + RELIABLE_FORECAST_HORIZON:
            warnings.append(
                "Departure is more than 48 hours away, so the weather forecast is less reliable."
            )

    if errors:
        raise TripValidationError(errors)

    assert origin_tz is not None and departure_utc is not None
    trip = TripRequest(
        origin=replace(origin, timezone=origin_tz),
        destination=replace(destination, timezone=destination_tz),
        departure_utc=departure_utc,
        departure_timezone=origin_tz,
        weight_lb=weight_lb,
        spacing_mi=spacing_mi,
    )
    return trip, warnings
