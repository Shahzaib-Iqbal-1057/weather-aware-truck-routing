from datetime import UTC, datetime, timedelta

import pytest

from tests.factories import make_route, path
from trips.domain.hours_of_service import StopKind
from trips.domain.timeline import build_timeline, checkpoint_miles

DEPART = datetime(2026, 10, 20, 13, 0, tzinfo=UTC)
H = 3600

# ~227 miles due east at constant speed, so miles and driving time are proportional.
SHORT = make_route(path((35.0, -100.0), (35.0, -96.0)), hours=4)
# ~1,250 miles, 20 h of driving: break at 8 h, rest at 11 h, break at 19 h.
LONG = make_route(path((35.0, -120.0), (35.0, -98.0), steps_per_leg=1000), hours=20)


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (35, [0, 10, 20, 30, 35]),
        (31, [0, 10, 20, 31]),  # 30 is within 2 mi of the end, so dropped
        (1.5, [0, 1.5]),
    ],
)
def test_checkpoint_miles(length, expected):
    assert checkpoint_miles(length, 10) == pytest.approx(expected)


def test_checkpoints_cover_the_whole_route_once():
    timeline = build_timeline(SHORT, DEPART, spacing_mi=10)
    first, second, last = timeline.checkpoints[0], timeline.checkpoints[1], timeline.checkpoints[-1]
    length_mi = SHORT.length_m / 1609.344

    assert (first.covers_from_mi, first.covers_to_mi) == (0, 5)
    assert (second.covers_from_mi, second.covers_to_mi) == (5, 15)
    assert last.covers_to_mi == pytest.approx(length_mi)
    assert sum(c.covered_miles for c in timeline.checkpoints) == pytest.approx(length_mi)
    for before, after in zip(timeline.checkpoints, timeline.checkpoints[1:], strict=False):
        assert before.covers_to_mi == after.covers_from_mi


def test_checkpoints_lie_on_the_route_at_their_mile():
    timeline = build_timeline(SHORT, DEPART, spacing_mi=10)

    assert timeline.checkpoints[0].position == (35.0, -100.0)
    assert timeline.checkpoints[-1].position == (35.0, -96.0)
    middle = timeline.checkpoints[len(timeline.checkpoints) // 2]
    assert middle.position[0] == pytest.approx(35.0)
    assert -100 < middle.position[1] < -96


def test_short_trip_eta_is_departure_plus_driving_time():
    timeline = build_timeline(SHORT, DEPART, spacing_mi=10)

    assert timeline.stops == []
    assert timeline.arrival == DEPART + timedelta(hours=4)
    for checkpoint in timeline.checkpoints:
        assert checkpoint.eta == DEPART + timedelta(seconds=checkpoint.driving_s)


def test_long_trip_etas_include_rest_stops():
    timeline = build_timeline(LONG, DEPART, spacing_mi=10)

    for checkpoint in timeline.checkpoints:
        driving_h = checkpoint.driving_s / H
        rest_before = 0.0 if driving_h <= 8 else 0.5 if driving_h <= 11 else 10.5
        rest_before += 0.5 if driving_h > 19 else 0
        assert checkpoint.eta == pytest.approx(
            DEPART + timedelta(hours=driving_h + rest_before), abs=timedelta(seconds=1)
        )


def test_rest_stops_are_placed_where_the_driving_clock_requires():
    timeline = build_timeline(LONG, DEPART, spacing_mi=10)
    length_mi = LONG.length_m / 1609.344

    assert [stop.kind for stop in timeline.stops] == [StopKind.BREAK, StopKind.REST, StopKind.BREAK]
    brk, rest, _ = timeline.stops
    assert brk.mile == pytest.approx(length_mi * 8 / 20, rel=1e-3)
    assert (brk.starts, brk.ends) == (DEPART + timedelta(hours=8), DEPART + timedelta(hours=8.5))
    assert rest.mile == pytest.approx(length_mi * 11 / 20, rel=1e-3)
    assert (rest.starts, rest.ends) == (
        DEPART + timedelta(hours=11.5),
        DEPART + timedelta(hours=21.5),
    )


def test_arrival_and_trip_time_include_every_stop():
    timeline = build_timeline(LONG, DEPART, spacing_mi=10)

    assert timeline.driving_s == 20 * H
    assert timeline.trip_s == pytest.approx(31 * H)
    assert timeline.arrival == DEPART + timedelta(hours=31)
