from datetime import UTC, datetime

import pytest

from tests.factories import make_route, path
from trips.domain.risk import CheckpointRisk, RiskLevel
from trips.domain.route_totals import route_totals
from trips.domain.timeline import build_timeline

DEPART = datetime(2026, 10, 20, 13, tzinfo=UTC)
# ~41 miles: checkpoints at 0, 10, 20, 30, 41.x → covering 5, 10, 10, ~10.7, ~5.7 miles.
ROUTE = make_route(path((35.0, -100.0), (35.0, -99.27)), hours=1)
TIMELINE = build_timeline(ROUTE, DEPART, spacing_mi=10)


def risk(level):
    return CheckpointRisk(
        level=level, wind=level, rain=RiskLevel.LOW, snow=RiskLevel.LOW, reasons=[]
    )


def totals_for(*levels):
    assert len(levels) == len(TIMELINE.checkpoints)
    return route_totals(
        ROUTE.length_m, TIMELINE, [risk(lv) if lv is not None else None for lv in levels]
    )


def test_miles_at_each_level_are_the_miles_their_checkpoints_cover():
    L, H, S = RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.SEVERE
    covered = [c.covered_miles for c in TIMELINE.checkpoints]

    totals = totals_for(L, H, S, S, L)

    assert totals.high_mi == pytest.approx(covered[1])
    assert totals.severe_mi == pytest.approx(covered[2] + covered[3])
    assert totals.no_travel_mi == 0 and not totals.has_no_travel


def test_average_is_mile_weighted_over_miles_with_a_forecast():
    L, M = RiskLevel.LOW, RiskLevel.MODERATE
    covered = [c.covered_miles for c in TIMELINE.checkpoints]

    totals = totals_for(M, L, None, L, L)

    known = sum(covered) - covered[2]
    assert totals.unknown_mi == pytest.approx(covered[2])
    assert totals.average_risk == pytest.approx(covered[0] * 1 / known)


def test_any_no_travel_checkpoint_marks_the_route():
    L, N = RiskLevel.LOW, RiskLevel.NO_TRAVEL
    totals = totals_for(L, L, N, L, L)
    assert totals.has_no_travel
    assert totals.no_travel_mi == pytest.approx(TIMELINE.checkpoints[2].covered_miles)


def test_no_forecast_at_all_has_no_average():
    totals = totals_for(None, None, None, None, None)
    assert totals.average_risk is None and not totals.has_forecast
    assert totals.unknown_mi == pytest.approx(ROUTE.length_m / 1609.344)


def test_door_to_door_time_comes_from_the_timeline():
    assert totals_for(*[RiskLevel.LOW] * 5).trip_s == TIMELINE.trip_s
