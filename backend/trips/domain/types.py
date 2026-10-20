from dataclasses import dataclass
from enum import StrEnum


class PlaceKind(StrEnum):
    CITY = "city"
    ADDRESS = "address"
    PLACE = "place"  # a named business or landmark


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float
    kind: PlaceKind = PlaceKind.PLACE
    timezone: str | None = None


@dataclass(frozen=True)
class Route:
    """A drivable route from the routing provider.

    `points` are (lat, lon). `distances_m` and `times_s` are cumulative from the origin,
    one value per point, so the position and ETA anywhere along the route can be found.
    """

    points: list[tuple[float, float]]
    distances_m: list[float]
    times_s: list[float]

    @property
    def length_m(self) -> float:
        return self.distances_m[-1]

    @property
    def travel_time_s(self) -> float:
        return self.times_s[-1]
