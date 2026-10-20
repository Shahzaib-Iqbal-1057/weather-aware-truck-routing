"""Stage 0: turn raw form input into a validated TripRequest.

All business rules for the input live here, so the API layer only parses types. Time zones are
looked up by the caller (it is file I/O), keeping this module pure.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from trips.domain.geo import haversine_miles
from trips.domain.types import Place

# The brief's "load weight" is the cargo (payload), not the whole truck: an empty tractor with a
# 53 ft trailer already weighs ~35,000 lb, so its 30,000 / 40,000 lb rules only make sense for
# cargo. Max cargo = 80,000 lb federal gross limit − 35,000 lb empty truck (see vehicle.py).
CARGO_MIN_LB = 0  # an empty (deadhead) trailer is a valid trip
CARGO_MAX_LB = 45_000
SPACING_OPTIONS_MI = (10, 25, 50)
# Weather is checked every 10 miles: close to the forecast model's own resolution, and still few
# enough points to batch into one weather request. 25 and 50 stay accepted by the API.
DEFAULT_SPACING_MI = 10
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
    cargo_weight_lb: int
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
    cargo_weight_lb: int,
    spacing_mi: int,
    origin_timezone: str | None,
    destination_timezone: str | None,
    now: datetime,
) -> tuple[TripRequest, list[str]]:
    """Validate the input and return the trip plus any non-blocking warnings.

    `departure_local` is a naive wall-clock time in the origin's time zone.
    Raises TripValidationError with one message per invalid field.
    """
    errors: dict[str, str] = {}

    if origin_timezone is None:
        errors["origin"] = "Could not determine the time zone for this origin."

    if haversine_miles(origin.lat, origin.lon, destination.lat, destination.lon) < MIN_TRIP_MILES:
        errors["destination"] = "Destination must be a different place from the origin."

    if not CARGO_MIN_LB <= cargo_weight_lb <= CARGO_MAX_LB:
        errors["cargo_weight_lb"] = (
            f"Cargo weight must be between {CARGO_MIN_LB:,} and {CARGO_MAX_LB:,} lb."
        )

    if spacing_mi not in SPACING_OPTIONS_MI:
        options = ", ".join(str(option) for option in SPACING_OPTIONS_MI)
        errors["spacing_mi"] = f"Checkpoint spacing must be one of {options} miles."

    warnings: list[str] = []
    departure_utc = None
    if departure_local.tzinfo is not None:
        errors["departure_local"] = "Departure time must not include a time zone offset."
    elif origin_timezone is not None:
        zone = ZoneInfo(origin_timezone)
        departure_utc = departure_local.replace(tzinfo=zone).astimezone(UTC)
        if departure_utc.astimezone(zone).replace(tzinfo=None) != departure_local:
            # e.g. 2:30 AM on the day clocks spring forward never happens there.
            errors["departure_local"] = (
                "That time is skipped when clocks change for daylight saving. Choose another time."
            )
        elif departure_utc < now - PAST_DEPARTURE_GRACE:
            errors["departure_local"] = "Departure time is in the past."
        elif departure_utc > now + MAX_DEPARTURE_AHEAD:
            errors["departure_local"] = "Departure must be within the next 7 days."
        elif departure_utc > now + RELIABLE_FORECAST_HORIZON:
            warnings.append(
                "Departure is more than 48 hours away, so the weather forecast is less reliable."
            )

    if errors:
        raise TripValidationError(errors)

    assert origin_timezone is not None and departure_utc is not None
    trip = TripRequest(
        origin=replace(origin, timezone=origin_timezone),
        destination=replace(destination, timezone=destination_timezone),
        departure_utc=departure_utc,
        departure_timezone=origin_timezone,
        cargo_weight_lb=cargo_weight_lb,
        spacing_mi=spacing_mi,
    )
    return trip, warnings
