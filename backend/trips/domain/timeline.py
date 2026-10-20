"""Stage 2: checkpoints along a route, with ETAs that include required rest stops.

- A checkpoint is placed every `spacing_mi` miles from the start, plus one at the destination.
  A regular checkpoint within SKIP_NEAR_END_MI of the destination is dropped (it would nearly
  duplicate the destination).
- Each checkpoint covers the road halfway to its neighbours on both sides, so the covered miles
  add up to the route length. Stage 5 counts risk miles from these.
- ETA = departure + driving time to the point (from the router) + rest stops taken before it.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timedelta

from trips.domain.geo import METERS_PER_MILE, LatLon
from trips.domain.hours_of_service import StopKind, elapsed_s, rest_schedule
from trips.domain.types import Route

SKIP_NEAR_END_MI = 2.0


@dataclass(frozen=True)
class Checkpoint:
    position: LatLon
    mile: float
    driving_s: float
    eta: datetime
    covers_from_mi: float
    covers_to_mi: float

    @property
    def covered_miles(self) -> float:
        return self.covers_to_mi - self.covers_from_mi


@dataclass(frozen=True)
class PlacedStop:
    kind: StopKind
    position: LatLon
    mile: float
    starts: datetime
    ends: datetime


@dataclass(frozen=True)
class RouteTimeline:
    checkpoints: list[Checkpoint]
    stops: list[PlacedStop]
    driving_s: float
    arrival: datetime

    @property
    def trip_s(self) -> float:
        """Door-to-door time, including rest stops."""
        return self.driving_s + sum((s.ends - s.starts).total_seconds() for s in self.stops)


def build_timeline(route: Route, departure: datetime, spacing_mi: float) -> RouteTimeline:
    stops = rest_schedule(route.travel_time_s)

    def eta(driving_s: float) -> datetime:
        return departure + timedelta(seconds=elapsed_s(driving_s, stops))

    miles = checkpoint_miles(route.length_m / METERS_PER_MILE, spacing_mi)
    checkpoints = []
    for i, mile in enumerate(miles):
        position, driving_s = _at_distance(route, mile * METERS_PER_MILE)
        checkpoints.append(
            Checkpoint(
                position=position,
                mile=mile,
                driving_s=driving_s,
                eta=eta(driving_s),
                covers_from_mi=(miles[i - 1] + mile) / 2 if i > 0 else 0.0,
                covers_to_mi=(mile + miles[i + 1]) / 2 if i < len(miles) - 1 else mile,
            )
        )

    placed = []
    for stop in stops:
        position, distance_m = _at_driving_time(route, stop.driving_s)
        starts = eta(stop.driving_s)
        placed.append(
            PlacedStop(
                kind=stop.kind,
                position=position,
                mile=distance_m / METERS_PER_MILE,
                starts=starts,
                ends=starts + timedelta(seconds=stop.duration_s),
            )
        )

    return RouteTimeline(
        checkpoints=checkpoints,
        stops=placed,
        driving_s=route.travel_time_s,
        arrival=eta(route.travel_time_s),
    )


def checkpoint_miles(length_mi: float, spacing_mi: float) -> list[float]:
    """0, spacing, 2×spacing, … and the destination; drops a mark too close to the end."""
    miles = []
    mark = 0.0
    while mark < length_mi - SKIP_NEAR_END_MI or mark == 0.0:
        miles.append(mark)
        mark += spacing_mi
    if length_mi > 0:
        miles.append(length_mi)
    return miles


def _at_distance(route: Route, distance_m: float) -> tuple[LatLon, float]:
    """Position and driving time at a distance along the route (linear between points)."""
    return _interpolate(route, route.distances_m, distance_m, route.times_s)


def _at_driving_time(route: Route, driving_s: float) -> tuple[LatLon, float]:
    """Position and distance at a driving time along the route (linear between points)."""
    return _interpolate(route, route.times_s, driving_s, route.distances_m)


def _interpolate(
    route: Route, keys: list[float], key: float, values: list[float]
) -> tuple[LatLon, float]:
    if key <= keys[0]:
        return route.points[0], values[0]
    if key >= keys[-1]:
        return route.points[-1], values[-1]
    hi = bisect_left(keys, key)
    lo = hi - 1
    span = keys[hi] - keys[lo]
    t = (key - keys[lo]) / span if span > 0 else 0.0
    (lat0, lon0), (lat1, lon1) = route.points[lo], route.points[hi]
    position = (lat0 + t * (lat1 - lat0), lon0 + t * (lon1 - lon0))
    return position, values[lo] + t * (values[hi] - values[lo])
