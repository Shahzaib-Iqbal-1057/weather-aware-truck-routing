import pytest

from tests.factories import make_route, path
from trips.domain.candidates import detour_boxes, label_points, select_routes, shared_fraction

START, END = (35.0, -100.0), (35.0, -96.0)  # ~225 miles east-west

DIRECT = path(START, END)
NORTH = path(START, (36.0, -98.0), END)
SOUTH = path(START, (34.0, -98.0), END)
FAR_NORTH = path(START, (37.5, -98.0), END)
# Same road as DIRECT for the first and last thirds, its own road in the middle.
PARTIAL = path(START, (35.0, -98.7), (35.6, -98.0), (35.0, -97.3), END)


def test_identical_routes_share_everything():
    route = make_route(DIRECT, hours=4)
    assert shared_fraction(route, route) == pytest.approx(1.0, abs=0.01)


def test_separate_corridors_share_little():
    assert shared_fraction(make_route(NORTH, 5), make_route(SOUTH, 5)) < 0.1


def test_partially_overlapping_routes_share_part_of_the_road():
    assert shared_fraction(make_route(PARTIAL, 4.3), make_route(DIRECT, 4)) == pytest.approx(
        0.65, abs=0.1
    )


def test_keeps_the_fastest_and_orders_by_time():
    south, direct, north = make_route(SOUTH, 4.6), make_route(DIRECT, 4), make_route(NORTH, 4.5)

    assert select_routes([south, direct, north]) == [direct, north, south]


def test_drops_routes_more_than_25_percent_slower():
    direct, north = make_route(DIRECT, 4), make_route(NORTH, 4.5)
    too_slow = make_route(SOUTH, 5.01)

    assert select_routes([direct, north, too_slow]) == [direct, north]


def test_drops_near_duplicates_of_a_chosen_route():
    direct = make_route(DIRECT, 4)
    duplicate = make_route([(lat + 0.001, lon) for lat, lon in DIRECT], 4.1)

    assert select_routes([direct, duplicate]) == [direct]


def test_prefers_the_most_different_route_over_a_faster_similar_one():
    direct = make_route(DIRECT, 4)
    partial = make_route(PARTIAL, 4.2)  # faster, but shares ~65% with DIRECT
    north, south = make_route(NORTH, 4.6), make_route(SOUTH, 4.7)  # slower, own corridors

    assert select_routes([direct, partial, north, south]) == [direct, north, south]


def test_returns_at_most_three_routes():
    routes = [
        make_route(p, h) for p, h in [(DIRECT, 4), (NORTH, 4.5), (SOUTH, 4.6), (FAR_NORTH, 4.9)]
    ]
    assert len(select_routes(routes)) == 3


def test_returns_nothing_for_no_candidates():
    assert select_routes([]) == []


def test_detour_box_sits_on_the_route_midpoint():
    route = make_route(DIRECT, 4)

    [box] = detour_boxes([route], at_fractions=(0.5,))

    assert box.contains((35.0, -98.0))
    assert not box.contains(START)
    assert not box.contains(END)


def test_detour_box_is_smaller_on_short_routes_and_skipped_if_it_would_cover_an_end():
    short = make_route(path((35.0, -100.0), (35.0, -99.9), steps_per_leg=20), hours=0.2)

    assert detour_boxes([short], at_fractions=(0.1,)) == []
    assert len(detour_boxes([short], at_fractions=(0.5,))) == 1


def test_labels_sit_on_road_only_that_route_uses():
    direct, partial = make_route(DIRECT, 4), make_route(PARTIAL, 4.3)

    direct_label, partial_label = label_points([direct, partial])

    # PARTIAL shares DIRECT's first and last thirds, so both labels belong in the middle third,
    # each on its own road: DIRECT along lat 35.0, PARTIAL up on its northern detour.
    assert -98.7 < direct_label[1] < -97.3
    assert direct_label[0] == pytest.approx(35.0, abs=0.01)
    assert partial_label[0] > 35.2


def test_label_falls_back_to_the_midpoint_when_every_part_is_shared():
    direct = make_route(DIRECT, 4)
    duplicate = make_route([(lat + 0.001, lon) for lat, lon in DIRECT], 4.1)

    label, _ = label_points([direct, duplicate])

    assert label[1] == pytest.approx(-98.0, abs=0.05)


def test_a_single_route_is_labelled_in_its_middle():
    [label] = label_points([make_route(DIRECT, 4)])
    assert label[1] == pytest.approx(-98.0, abs=0.05)
