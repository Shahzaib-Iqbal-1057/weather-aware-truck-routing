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
