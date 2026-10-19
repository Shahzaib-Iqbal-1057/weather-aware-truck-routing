import pytest

from trips.domain.geo import box_around, haversine_miles, simplify


def test_haversine_matches_known_distance():
    # Dallas to Denver, straight line: about 663 miles.
    assert haversine_miles(32.7767, -96.7970, 39.7392, -104.9903) == pytest.approx(663, abs=3)


def test_box_around_is_square_in_meters():
    box = box_around((40.0, -100.0), half_size_m=70_000)

    assert box.contains((40.0, -100.0))
    assert box.north - box.south == pytest.approx(2 * 70_000 / 111_320)
    # Longitude degrees are shorter at 40°N, so the box spans more of them.
    assert box.east - box.west > box.north - box.south


def test_simplify_drops_points_on_a_straight_line():
    points = [(40.0, -100.0 + i * 0.01) for i in range(100)]
    assert simplify(points, tolerance_m=10) == [points[0], points[-1]]


def test_simplify_keeps_corners_and_endpoints():
    corner = (40.5, -100.0)
    points = [(40.0 + i * 0.05, -100.0) for i in range(10)] + [corner]
    points += [(40.5, -100.0 + i * 0.05) for i in range(1, 10)]

    simplified = simplify(points, tolerance_m=10)

    assert simplified[0] == points[0]
    assert simplified[-1] == points[-1]
    assert corner in simplified
    assert len(simplified) == 3


def test_simplify_leaves_short_lines_alone():
    points = [(40.0, -100.0), (40.1, -100.1)]
    assert simplify(points, tolerance_m=10) == points
