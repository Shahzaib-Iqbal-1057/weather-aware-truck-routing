"""Driver rest breaks required by US hours-of-service rules (FMCSA, property-carrying drivers).

Model (solo driver who starts the trip fresh):
- a 30-minute break after 8 hours of driving;
- a 10-hour rest after 11 hours of driving, which starts a new shift;
- repeated for every shift until arrival.

The 30-minute break is not driving time, so a shift is 11 h of driving in 11.5 h, inside the
14-hour on-duty window. Weekly (60/70-hour) limits are not modelled.
"""

from dataclasses import dataclass
from enum import StrEnum

HOUR_S = 3600.0
DRIVING_BEFORE_BREAK_S = 8 * HOUR_S
BREAK_S = 0.5 * HOUR_S
DRIVING_PER_SHIFT_S = 11 * HOUR_S
REST_S = 10 * HOUR_S


class StopKind(StrEnum):
    BREAK = "break"  # 30 minutes
    REST = "rest"  # 10 hours


@dataclass(frozen=True)
class RestStop:
    kind: StopKind
    driving_s: float  # driving time since departure when the stop starts
    duration_s: float


def rest_schedule(total_driving_s: float) -> list[RestStop]:
    """Stops needed to drive `total_driving_s`. None is needed if arrival comes first."""
    stops: list[RestStop] = []
    shift_start = 0.0
    while True:
        break_at = shift_start + DRIVING_BEFORE_BREAK_S
        if break_at >= total_driving_s:
            return stops
        stops.append(RestStop(StopKind.BREAK, break_at, BREAK_S))

        shift_end = shift_start + DRIVING_PER_SHIFT_S
        if shift_end >= total_driving_s:
            return stops
        stops.append(RestStop(StopKind.REST, shift_end, REST_S))
        shift_start = shift_end


def elapsed_s(driving_s: float, stops: list[RestStop]) -> float:
    """Clock time from departure until the truck has driven `driving_s`.

    Stops starting exactly at `driving_s` are not included: the truck arrives, then stops.
    """
    return driving_s + sum(stop.duration_s for stop in stops if stop.driving_s < driving_s)
