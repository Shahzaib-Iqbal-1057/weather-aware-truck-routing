from datetime import UTC, datetime

import pytest

from tests.factories import make_route, path
from trips.domain.geo import METERS_PER_MILE, haversine_meters
from trips.domain.risk import CheckpointRisk, RiskLevel
from trips.domain.risk_stretches import risk_stretches
from trips.domain.timeline import build_timeline

DEPART = datetime(2026, 10, 20, 13, tzinfo=UTC)
# ~41 miles: checkpoints at 0, 10, 20, 30, 41.x.
ROUTE = make_route(path((35.0, -100.0), (35.0, -99.27)), hours=1)
TIMELINE = build_timeline(ROUTE, DEPART, spacing_mi=10)
L, M, H, S = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE


def risk(level):
    return CheckpointRisk(
        level=level, wind=level, rain=RiskLevel.LOW, snow=RiskLevel.LOW, reasons=[]
    )


def stretches_for(*levels):
    return risk_stretches(ROUTE, TIMELINE, [risk(lv) if lv is not None else None for lv in levels])


def test_a_calm_route_has_no_stretches():
    assert stretches_for(L, L, L, L, L) == []


def test_neighbours_at_the_same_level_merge_and_low_or_unknown_are_left_out():
    stretches = stretches_for(M, H, H, None, S)

    assert [(s.level, s.from_mi, s.to_mi) for s in stretches] == [
        (M, 0.0, 5.0),
        (H, 5.0, 25.0),
        (S, TIMELINE.checkpoints[4].covers_from_mi, TIMELINE.checkpoints[4].covers_to_mi),
    ]


def test_each_stretch_follows_the_road_between_its_miles():
    (stretch,) = stretches_for(L, H, H, L, L)

    along = sum(
        haversine_meters(a, b) for a, b in zip(stretch.points, stretch.points[1:], strict=False)
    )
    assert along / METERS_PER_MILE == pytest.approx(20.0, abs=0.01)
    assert stretch.points[0] != stretch.points[1]
