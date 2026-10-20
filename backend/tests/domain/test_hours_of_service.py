import pytest

from trips.domain.hours_of_service import StopKind, elapsed_s, rest_schedule

H = 3600


def kinds_and_times(total_hours):
    return [(stop.kind, stop.driving_s / H) for stop in rest_schedule(total_hours * H)]


@pytest.mark.parametrize("hours", [0.5, 7.9, 8.0])
def test_no_stop_when_arriving_within_eight_hours(hours):
    assert rest_schedule(hours * H) == []


def test_30_minute_break_after_8_hours():
    assert kinds_and_times(10) == [(StopKind.BREAK, 8)]


def test_10_hour_rest_after_11_hours_of_driving():
    assert kinds_and_times(12.33) == [(StopKind.BREAK, 8), (StopKind.REST, 11)]


def test_pattern_repeats_each_shift():
    # Second shift starts at 11 h of driving: break at 19 h, rest at 22 h. Arrival at 30 h
    # comes exactly when a third break would be due, so none is needed.
    assert kinds_and_times(30) == [
        (StopKind.BREAK, 8),
        (StopKind.REST, 11),
        (StopKind.BREAK, 19),
        (StopKind.REST, 22),
    ]


def test_stop_durations():
    brk, rest = rest_schedule(12 * H)
    assert brk.duration_s == 0.5 * H
    assert rest.duration_s == 10 * H


def test_elapsed_time_adds_stops_taken_before_the_point():
    stops = rest_schedule(20 * H)  # break at 8 h, rest at 11 h, break at 19 h

    assert elapsed_s(5 * H, stops) == 5 * H
    assert elapsed_s(8 * H, stops) == 8 * H  # arrives at the break, then stops
    assert elapsed_s(9 * H, stops) == 9.5 * H
    assert elapsed_s(12 * H, stops) == 22.5 * H
    assert elapsed_s(20 * H, stops) == 31 * H
