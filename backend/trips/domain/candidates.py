"""Stage 1: choose up to 3 meaningfully different candidate routes.

The rules follow the "admissible alternative" definition of Abraham, Delling, Goldberg and
Werneck, "Alternative Routes in Road Networks" (SEA 2010), with their parameter values:

- Bounded stretch: an alternative takes at most 25% longer than the fastest route.
- Limited sharing: an alternative shares at most 80% of its road with a route already chosen.

The paper applies the stretch limit to every part of the detour. A routing API only gives whole
routes, so we apply it to the whole trip.
"""

from bisect import bisect_left
from itertools import pairwise
from math import floor

from trips.domain.geo import BoundingBox, LatLon, box_around
from trips.domain.types import Route

MAX_ROUTES = 3
MAX_STRETCH = 0.25
MAX_SHARING = 0.80

# Sharing is measured by sampling a route every SAMPLE_STEP_M and checking whether each sample
# lies on the other route, using a grid of ~1 km cells (with neighbours, to absorb small offsets
# between two routes' points on the same road).
SAMPLE_STEP_M = 500.0
CELL_DEG = 0.01

# Fallback: ask the router to avoid a box on each chosen route. TomTom allows ~160 km per side.
AVOID_BOX_HALF_SIZE_M = 70_000.0
AVOID_BOX_MAX_ROUTE_FRACTION = 0.15


def select_routes(candidates: list[Route], max_routes: int = MAX_ROUTES) -> list[Route]:
    """Fastest route first, then repeatedly the most different admissible one.

    Returns routes ordered by travel time.
    """
    if not candidates:
        return []

    fastest = min(candidates, key=lambda route: route.travel_time_s)
    time_limit = fastest.travel_time_s * (1 + MAX_STRETCH)
    footprints = {id(route): _Footprint(route) for route in candidates}

    selected = [fastest]
    pool = [r for r in candidates if r is not fastest and r.travel_time_s <= time_limit]
    while len(selected) < max_routes:
        best: tuple[tuple[float, float], Route] | None = None
        for route in pool:
            if any(route is chosen for chosen in selected):
                continue
            sharing = max(
                footprints[id(route)].shared_fraction(footprints[id(chosen)]) for chosen in selected
            )
            if sharing > MAX_SHARING:
                continue
            rank = (sharing, route.travel_time_s)  # most different first, faster breaks ties
            if best is None or rank < best[0]:
                best = (rank, route)
        if best is None:
            break
        selected.append(best[1])

    return sorted(selected, key=lambda route: route.travel_time_s)


def shared_fraction(route: Route, reference: Route) -> float:
    """Share of `reference`'s length that `route` also drives on (0–1)."""
    return _Footprint(route).shared_fraction(_Footprint(reference))


def detour_boxes(routes: list[Route], at_fractions: tuple[float, ...]) -> list[BoundingBox]:
    """Boxes on each route (at the given fractions of its length) for the router to avoid.

    Boxes covering the origin or destination are skipped, since the trip could not avoid them.
    """
    boxes = []
    for route in routes:
        half_size = min(AVOID_BOX_HALF_SIZE_M, route.length_m * AVOID_BOX_MAX_ROUTE_FRACTION)
        for fraction in at_fractions:
            box = box_around(point_at_distance(route, route.length_m * fraction), half_size)
            if not box.contains(route.points[0]) and not box.contains(route.points[-1]):
                boxes.append(box)
    return boxes


def point_at_distance(route: Route, distance_m: float) -> LatLon:
    index = min(bisect_left(route.distances_m, distance_m), len(route.points) - 1)
    return route.points[index]


def _cell(point: LatLon) -> tuple[int, int]:
    return floor(point[0] / CELL_DEG), floor(point[1] / CELL_DEG)


class _Footprint:
    def __init__(self, route: Route):
        self.length_m = route.length_m
        self.samples = _sample(route)
        self.cells: set[tuple[int, int]] = set()
        for sample in self.samples:
            row, col = _cell(sample)
            self.cells.update((row + dr, col + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1))

    def shared_fraction(self, reference: "_Footprint") -> float:
        if reference.length_m <= 0:
            return 1.0
        on_reference = sum(1 for sample in self.samples if _cell(sample) in reference.cells)
        return min(1.0, on_reference * SAMPLE_STEP_M / reference.length_m)


def _sample(route: Route) -> list[LatLon]:
    """Points every SAMPLE_STEP_M along the route, so each sample stands for the same length.

    Route points are not evenly spaced (long straight highways may have kilometres between
    points), so samples are interpolated along each segment.
    """
    samples = []
    next_mark = 0.0
    for (a, b), (start_m, end_m) in zip(
        pairwise(route.points), pairwise(route.distances_m), strict=True
    ):
        while next_mark <= end_m and end_m > start_m:
            t = (next_mark - start_m) / (end_m - start_m)
            samples.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            next_mark += SAMPLE_STEP_M
    return samples
