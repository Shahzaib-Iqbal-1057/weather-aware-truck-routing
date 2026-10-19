import hashlib
from dataclasses import replace

from django.conf import settings
from django.core.cache import cache

from trips.domain.timezones import timezone_at
from trips.domain.types import Place
from trips.providers.base import Geocoder
from trips.providers.tomtom_search import TomTomGeocoder

CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_LIMIT = 6


def get_geocoder() -> Geocoder:
    return TomTomGeocoder(settings.TOMTOM_API_KEY)


def search_places(
    query: str, *, limit: int = DEFAULT_LIMIT, geocoder: Geocoder | None = None
) -> list[Place]:
    """Autocomplete suggestions for a partial query, each tagged with its time zone.

    Results are cached because every keystroke-pause costs a request from the daily quota.
    """
    normalized = " ".join(query.split()).lower()
    cache_key = "geocode:" + hashlib.sha256(f"{normalized}|{limit}".encode()).hexdigest()

    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    places = (geocoder or get_geocoder()).search(normalized, limit=limit)
    places = [replace(place, timezone=timezone_at(place.lat, place.lon)) for place in places]
    cache.set(cache_key, places, CACHE_TTL_SECONDS)
    return places
