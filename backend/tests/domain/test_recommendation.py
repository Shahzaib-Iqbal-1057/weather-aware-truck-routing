import pytest

from trips.domain.recommendation import recommend
from trips.domain.route_totals import RouteTotals

H = 3600
IDS = ["A", "B", "C"]


def totals(hours, severe=0.0, high=0.0, average=0.0, no_travel=0.0, length=400.0, unknown=0.0):
    return RouteTotals(
        length_mi=length,
        trip_s=hours * H,
        severe_mi=severe,
        high_mi=high,
        no_travel_mi=no_travel,
        unknown_mi=unknown,
        average_risk=average,
    )


def pick(*routes):
    result = recommend(list(routes), IDS[: len(routes)], spacing_mi=10)
    return (IDS[result.route_index] if result.route_index is not None else None), result.reason


def test_calm_weather_picks_the_fastest():
    choice, reason = pick(totals(12), totals(13), totals(12.5))
    assert choice == "A"
    assert (
        reason
        == "Route A: weather risk is practically the same on every route, and A is the fastest."
    )


def test_fewest_severe_miles_wins_even_if_slower():
    choice, reason = pick(totals(12, severe=40, high=10), totals(13, severe=0, high=30))
    assert choice == "B"
    assert reason == "Route B: fewer Severe miles than A (0 vs 40); 1 h slower than A."


def test_severe_miles_are_compared_exactly():
    # 10 Severe miles is one checkpoint, but it is never treated as noise.
    assert pick(totals(12, severe=10), totals(15, severe=0))[0] == "B"


def test_with_equal_severe_miles_fewest_high_miles_wins():
    choice, reason = pick(totals(12, severe=10, high=30), totals(12.5, severe=10, high=10))
    assert choice == "B"
    assert reason == (
        "Route B: as few Severe miles as A and fewer High miles (10 vs 30); 30 min slower than A."
    )


def test_one_moderate_checkpoint_more_is_a_tie_so_the_faster_route_wins():
    # The user's example: A has one Moderate checkpoint (10 mi at level 1 on 400 mi = 0.025),
    # B has none. A difference of exactly one checkpoint is within the margin.
    choice, reason = pick(totals(12, average=10 / 400), totals(13.2, average=0.0))
    assert choice == "A"
    assert "practically the same" in reason


def test_two_moderate_checkpoints_more_is_real_so_the_calmer_route_wins():
    choice, reason = pick(totals(12, average=20 / 400), totals(13.2, average=0.0))
    assert choice == "B"
    assert reason == (
        "Route B: less weather overall than A (average risk 0.00 vs 0.05); "
        "1 h 12 min slower than A."
    )


def test_the_margin_is_one_checkpoint_on_that_routes_own_length():
    # On an 800-mile route one checkpoint is 0.0125, so a 0.02 difference is real.
    assert pick(totals(12, average=0.02, length=800), totals(13, average=0.0, length=800))[0] == "B"
    assert (
        pick(totals(12, average=0.012, length=800), totals(13, average=0.0, length=800))[0] == "A"
    )


def test_on_short_trips_the_margin_is_at_most_a_quarter_level():
    # 8 miles: one checkpoint would be 10/8 = 1.25 levels. All-Moderate vs all-Low is not a tie.
    choice, _ = pick(totals(0.2, average=1.0, length=8), totals(0.25, average=0.0, length=8))
    assert choice == "B"
    assert pick(totals(0.2, average=0.2, length=8), totals(0.25, average=0.0, length=8))[0] == "A"


def test_no_travel_routes_are_never_recommended():
    choice, reason = pick(totals(10, no_travel=10), totals(11, high=20))
    assert choice == "B"
    assert reason == "Route B: avoids the No Travel conditions on A; 1 h slower than A."


def test_nothing_is_recommended_when_every_route_is_no_travel():
    choice, reason = pick(totals(10, no_travel=10), totals(11, no_travel=20))
    assert choice is None
    assert reason.startswith("Every route crosses No Travel conditions")


def test_nothing_is_recommended_without_any_weather():
    no_forecast = dict(average=None, unknown=400)
    choice, reason = pick(totals(10, **no_forecast), totals(11, **no_forecast))
    assert choice is None
    assert reason == "Weather is unavailable, so the routes can't be compared for safety."


def test_a_route_without_any_forecast_is_not_recommended_over_one_with_data():
    choice, reason = pick(totals(10, average=None, unknown=400), totals(11, average=0.1))
    assert choice == "B"
    assert reason == "Route B: A has no forecast to compare; 1 h slower than A."


def test_the_fastest_route_can_also_be_the_safest():
    choice, reason = pick(totals(12, average=0.0), totals(13, high=30, average=0.3))
    assert choice == "A"
    assert reason == "Route A: the fastest route, and it has the least weather risk."


def test_a_single_route_says_so_and_mentions_missing_forecast():
    choice, reason = pick(totals(12, unknown=12.4))
    assert choice == "A"
    assert reason == "Route A: the only truck route for this trip. No forecast for 12 mi of it."


@pytest.mark.parametrize("hours", [12, 12.0001])
def test_equal_or_near_equal_times_do_not_crash(hours):
    assert pick(totals(12), totals(hours))[0] in {"A", "B"}
