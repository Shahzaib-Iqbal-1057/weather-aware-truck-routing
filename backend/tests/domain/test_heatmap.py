import pytest

from tests.factories import make_route, path
from trips.domain.geo import haversine_meters
from trips.domain.heatmap import corridor_cells

ROUTE = make_route(path((35.0, -100.0), (35.0, -98.0), steps_per_leg=400), hours=3)  # ~113 mi


def test_cells_lie_within_the_corridor_of_the_route():
    cell_deg, centers = corridor_cells([ROUTE], corridor_km=50, max_cells=1_000)

    assert cell_deg == 0.25
    for lat, lon in centers:
        nearest = min(haversine_meters((lat, lon), p) for p in ROUTE.points)
        assert nearest <= 50_000 + 1_000  # 50 km, allowing for route sampling
    assert all(34.5 < lat < 35.5 for lat, _ in centers)


def test_cell_centers_sit_on_a_fixed_global_grid():
    _, centers = corridor_cells([ROUTE], corridor_km=50, max_cells=1_000)
    for lat, lon in centers:
        assert (lat / 0.25 - 0.5) == pytest.approx(round(lat / 0.25 - 0.5))
        assert (lon / 0.25 - 0.5) == pytest.approx(round(lon / 0.25 - 0.5))


def test_the_same_area_always_gives_the_same_cells():
    shifted = make_route([(lat + 0.001, lon) for lat, lon in ROUTE.points], hours=3)
    assert corridor_cells([ROUTE], 50, 1_000) == corridor_cells([shifted], 50, 1_000)


def test_coarser_cells_are_used_to_stay_under_the_cap():
    fine_deg, fine = corridor_cells([ROUTE], corridor_km=50, max_cells=1_000)
    coarse_deg, coarse = corridor_cells([ROUTE], corridor_km=50, max_cells=len(fine) - 1)

    assert (fine_deg, coarse_deg) == (0.25, 0.5)
    assert len(coarse) < len(fine)


def test_overlapping_routes_do_not_duplicate_cells():
    _, once = corridor_cells([ROUTE], 50, 1_000)
    _, twice = corridor_cells([ROUTE, ROUTE], 50, 1_000)
    assert once == twice
