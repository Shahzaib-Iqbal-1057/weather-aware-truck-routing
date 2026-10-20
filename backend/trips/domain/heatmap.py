"""Stage 8: the grid of weather-map cells along the trip corridor.

Cells sit on a fixed global grid (their centers are always at the same coordinates), so trips that
pass the same area share cached forecasts. Only cells whose center is within the corridor distance
of some route are kept. The cell size is the finest that keeps the count under the cap: storm
systems that matter for trucks are tens to hundreds of km across, so 0.5° (~50 km) cells still
show them on long trips.
"""

from math import cos, floor, radians

from trips.domain.geo import LatLon, haversine_meters
from trips.domain.types import Route

CELL_SIZES_DEG = (0.25, 0.5, 1.0)  # finest first
SAMPLE_EVERY_M = 10_000.0
KM_PER_DEGREE_LAT = 111.32


def corridor_cells(
    routes: list[Route], corridor_km: float, max_cells: int
) -> tuple[float, list[LatLon]]:
    """(cell size in degrees, cell centers) for the finest size with at most `max_cells` cells.

    Falls back to the coarsest size even if it is over the cap.
    """
    samples = [point for route in routes for point in _sample(route)]
    for cell_deg in CELL_SIZES_DEG:
        centers = _cells_near(samples, corridor_km, cell_deg)
        if len(centers) <= max_cells:
            return cell_deg, centers
    return cell_deg, centers


def _sample(route: Route) -> list[LatLon]:
    """Route points about every 10 km (always including both ends)."""
    samples = [route.points[0]]
    last_distance = 0.0
    for point, distance in zip(route.points, route.distances_m, strict=True):
        if distance - last_distance >= SAMPLE_EVERY_M:
            samples.append(point)
            last_distance = distance
    samples.append(route.points[-1])
    return samples


def _cells_near(samples: list[LatLon], corridor_km: float, cell_deg: float) -> list[LatLon]:
    found: set[tuple[int, int]] = set()
    for sample in samples:
        for row, col in _cells_in_reach(sample, corridor_km, cell_deg):
            if (row, col) in found:
                continue
            if haversine_meters(sample, _center(row, col, cell_deg)) <= corridor_km * 1000:
                found.add((row, col))
    return sorted(_center(row, col, cell_deg) for row, col in found)


def _cells_in_reach(point: LatLon, corridor_km: float, cell_deg: float):
    """Grid indices of every cell in the box `corridor_km` around `point`."""
    lat, lon = point
    lat_reach = corridor_km / KM_PER_DEGREE_LAT
    lon_reach = corridor_km / (KM_PER_DEGREE_LAT * max(cos(radians(lat)), 0.1))
    rows = range(floor((lat - lat_reach) / cell_deg), floor((lat + lat_reach) / cell_deg) + 1)
    cols = range(floor((lon - lon_reach) / cell_deg), floor((lon + lon_reach) / cell_deg) + 1)
    return ((row, col) for row in rows for col in cols)


def _center(row: int, col: int, cell_deg: float) -> LatLon:
    return round((row + 0.5) * cell_deg, 4), round((col + 0.5) * cell_deg, 4)
