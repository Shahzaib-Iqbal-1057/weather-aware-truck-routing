from functools import cache

from timezonefinder import TimezoneFinder


@cache
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def timezone_at(lat: float, lon: float) -> str | None:
    """IANA time zone name at a point, e.g. "America/Denver" (an "Etc/GMT±N" zone at sea).

    Returns None only if the lookup has no answer at all.
    """
    return _finder().timezone_at(lat=lat, lng=lon)
