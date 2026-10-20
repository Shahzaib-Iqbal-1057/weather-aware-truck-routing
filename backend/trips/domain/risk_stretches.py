"""Stage 7: the stretches of road drawn in risk colours on the map.

Each checkpoint covers the road halfway to its neighbours (see timeline.py). Neighbouring
checkpoints at the same level are merged into one stretch, and only Moderate or worse is kept:
the map draws those on top of the route line, so a calm route stays a plain line.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from trips.domain.geo import METERS_PER_MILE, LatLon
from trips.domain.risk import CheckpointRisk, RiskLevel
from trips.domain.timeline import RouteTimeline, position_at
from trips.domain.types import Route


@dataclass(frozen=True)
class RiskStretch:
    level: RiskLevel
    from_mi: float
    to_mi: float
    points: list[LatLon]


def risk_stretches(
    route: Route, timeline: RouteTimeline, risks: list[CheckpointRisk | None]
) -> list[RiskStretch]:
    merged: list[tuple[RiskLevel, float, float]] = []
    for checkpoint, risk in zip(timeline.checkpoints, risks, strict=True):
        if risk is None or risk.level < RiskLevel.MODERATE or checkpoint.covered_miles <= 0:
            continue
        start, end = checkpoint.covers_from_mi, checkpoint.covers_to_mi
        if merged and merged[-1][0] == risk.level and merged[-1][2] == start:
            merged[-1] = (risk.level, merged[-1][1], end)
        else:
            merged.append((risk.level, start, end))
    return [
        RiskStretch(
            level, start, end, _slice(route, start * METERS_PER_MILE, end * METERS_PER_MILE)
        )
        for level, start, end in merged
    ]


def _slice(route: Route, start_m: float, end_m: float) -> list[LatLon]:
    """The route's points strictly between two distances, with interpolated ends."""
    lo = bisect_right(route.distances_m, start_m)
    hi = bisect_left(route.distances_m, end_m)
    return [position_at(route, start_m), *route.points[lo:hi], position_at(route, end_m)]
