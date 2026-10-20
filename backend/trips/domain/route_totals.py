"""Stage 5: the numbers the recommendation compares, per route.

Each checkpoint covers the road halfway to its neighbours (see timeline.py), so miles at each
risk level are the sum of the miles covered by checkpoints at that level. Checkpoints without a
forecast are left out of every total and of the average, and reported as unknown miles: counting
them as Low would hide risk, counting them as Severe would invent it.
"""

from dataclasses import dataclass

from trips.domain.geo import METERS_PER_MILE
from trips.domain.risk import CheckpointRisk, RiskLevel
from trips.domain.timeline import RouteTimeline


@dataclass(frozen=True)
class RouteTotals:
    length_mi: float
    trip_s: float  # door to door, including driver rest stops
    severe_mi: float
    high_mi: float
    no_travel_mi: float
    unknown_mi: float
    # Mile-weighted mean level over miles with a forecast (Low 0, Moderate 1, High 2, Severe 3,
    # No Travel 4). None when no mile has a forecast.
    average_risk: float | None

    @property
    def has_no_travel(self) -> bool:
        return self.no_travel_mi > 0

    @property
    def has_forecast(self) -> bool:
        return self.average_risk is not None


def route_totals(
    length_m: float, timeline: RouteTimeline, risks: list[CheckpointRisk | None]
) -> RouteTotals:
    miles_at: dict[RiskLevel, float] = dict.fromkeys(RiskLevel, 0.0)
    unknown = 0.0
    for checkpoint, risk in zip(timeline.checkpoints, risks, strict=True):
        if risk is None:
            unknown += checkpoint.covered_miles
        else:
            miles_at[risk.level] += checkpoint.covered_miles

    known = sum(miles_at.values())
    average = sum(level * miles for level, miles in miles_at.items()) / known if known else None
    return RouteTotals(
        length_mi=length_m / METERS_PER_MILE,
        trip_s=timeline.trip_s,
        severe_mi=miles_at[RiskLevel.SEVERE],
        high_mi=miles_at[RiskLevel.HIGH],
        no_travel_mi=miles_at[RiskLevel.NO_TRAVEL],
        unknown_mi=unknown,
        average_risk=average,
    )
