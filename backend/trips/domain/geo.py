from collections.abc import Sequence
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_MI = 3958.8
EARTH_RADIUS_M = 6_371_008.8
METERS_PER_DEGREE_LAT = 111_320.0

LatLon = tuple[float, float]


@dataclass(frozen=True)
class BoundingBox:
    south: float
    west: float
    north: float
    east: float

    def contains(self, point: LatLon) -> bool:
        lat, lon = point
        return self.south <= lat <= self.north and self.west <= lon <= self.east


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in miles."""
    return _haversine(lat1, lon1, lat2, lon2) * EARTH_RADIUS_MI


def haversine_meters(a: LatLon, b: LatLon) -> float:
    return _haversine(a[0], a[1], b[0], b[1]) * EARTH_RADIUS_M


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Central angle between two points, in radians."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * asin(sqrt(a))


def box_around(center: LatLon, half_size_m: float) -> BoundingBox:
    lat, lon = center
    d_lat = half_size_m / METERS_PER_DEGREE_LAT
    d_lon = half_size_m / (METERS_PER_DEGREE_LAT * cos(radians(lat)))
    return BoundingBox(south=lat - d_lat, west=lon - d_lon, north=lat + d_lat, east=lon + d_lon)


def simplify(points: Sequence[LatLon], tolerance_m: float) -> list[LatLon]:
    """Ramer–Douglas–Peucker: drop points that deviate less than `tolerance_m` from the line.

    Uses a local flat projection, which is accurate enough at the tolerances used for display.
    """
    if len(points) < 3:
        return list(points)

    ref_lat = radians(sum(lat for lat, _ in points) / len(points))
    xy = [
        (lon * cos(ref_lat) * METERS_PER_DEGREE_LAT, lat * METERS_PER_DEGREE_LAT)
        for lat, lon in points
    ]

    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        index, distance = _farthest_from_segment(xy, start, end)
        if distance > tolerance_m:
            keep[index] = True
            stack.append((start, index))
            stack.append((index, end))

    return [point for point, kept in zip(points, keep, strict=True) if kept]


def _farthest_from_segment(
    xy: list[tuple[float, float]], start: int, end: int
) -> tuple[int, float]:
    (x1, y1), (x2, y2) = xy[start], xy[end]
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    best_index, best_distance = start, 0.0
    for i in range(start + 1, end):
        px, py = xy[i]
        if length_sq == 0:
            distance = sqrt((px - x1) ** 2 + (py - y1) ** 2)
        else:
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
            distance = sqrt((px - (x1 + t * dx)) ** 2 + (py - (y1 + t * dy)) ** 2)
        if distance > best_distance:
            best_index, best_distance = i, distance
    return best_index, best_distance
