"""Builders for synthetic routes with known geometry."""

from trips.domain.geo import haversine_meters
from trips.domain.types import Route


def line(
    start: tuple[float, float], end: tuple[float, float], steps: int
) -> list[tuple[float, float]]:
    return [
        (start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps)
        for i in range(steps + 1)
    ]


def path(*corners: tuple[float, float], steps_per_leg: int = 200) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for a, b in zip(corners, corners[1:], strict=False):
        segment = line(a, b, steps_per_leg)
        points.extend(segment if not points else segment[1:])
    return points


def make_route(
    points: list[tuple[float, float]], hours: float, traffic_delay_s: float = 0
) -> Route:
    distances = [0.0]
    for a, b in zip(points, points[1:], strict=False):
        distances.append(distances[-1] + haversine_meters(a, b))
    total_s = hours * 3600
    times = [total_s * d / distances[-1] for d in distances]
    return Route(
        points=points, distances_m=distances, times_s=times, traffic_delay_s=traffic_delay_s
    )
