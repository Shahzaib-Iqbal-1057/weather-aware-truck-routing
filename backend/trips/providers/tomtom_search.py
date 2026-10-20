"""Geocoding via TomTom Search API (TomTom Maps / "Genesis"), Fuzzy Search in typeahead mode."""

from typing import Any
from urllib.parse import quote

import requests

from trips.domain.types import Place, PlaceKind
from trips.providers.base import MALFORMED_RESPONSE_ERRORS, ProviderError

SEARCH_URL = "https://api.tomtom.com/search/2/search/{query}.json"

_ADDRESS_TYPES = {"Point Address", "Address Range", "Street", "Cross Street"}
# Geography results that make sense as a trip endpoint. States, counties and countries do not.
_USABLE_GEOGRAPHY = {"Municipality", "MunicipalitySubdivision", "Neighbourhood", "PostalCodeArea"}


class TomTomGeocoder:
    def __init__(
        self, api_key: str, *, session: requests.Session | None = None, timeout: float = 5
    ):
        self._api_key = api_key
        self._session = session or requests.Session()
        self._timeout = timeout

    def search(self, query: str, *, limit: int) -> list[Place]:
        if not self._api_key:
            raise ProviderError("TomTom API key is not configured.")

        params = {
            "key": self._api_key,
            "typeahead": "true",
            "countrySet": "US",
            "language": "en-US",
            # Ask for extra results because some (states, counties) are filtered out.
            "limit": min(limit * 2, 20),
        }
        try:
            response = self._session.get(
                SEARCH_URL.format(query=quote(query, safe="")), params=params, timeout=self._timeout
            )
        except requests.RequestException as exc:
            raise ProviderError(f"TomTom search request failed: {type(exc).__name__}") from None

        if response.status_code != 200:
            raise ProviderError(f"TomTom search failed with HTTP {response.status_code}.")

        try:
            return parse_search_results(response.json())[:limit]
        except MALFORMED_RESPONSE_ERRORS:
            raise ProviderError("TomTom search returned an unexpected response.") from None


def parse_search_results(payload: dict[str, Any]) -> list[Place]:
    places: list[Place] = []
    seen_labels: set[str] = set()
    for result in payload.get("results", []):
        place = _to_place(result)
        if place and place.label not in seen_labels:
            seen_labels.add(place.label)
            places.append(place)
    return places


def _to_place(result: dict[str, Any]) -> Place | None:
    result_type = result.get("type")
    address = result.get("address", {}).get("freeformAddress", "")

    if result_type == "Geography":
        if result.get("entityType") not in _USABLE_GEOGRAPHY:
            return None
        kind, label = PlaceKind.CITY, address
    elif result_type in _ADDRESS_TYPES:
        kind, label = PlaceKind.ADDRESS, address
    elif result_type == "POI":
        name = result.get("poi", {}).get("name", "")
        kind, label = PlaceKind.PLACE, f"{name}, {address}" if name else address
    else:
        return None

    lat, lon = _routable_position(result)
    if not label or lat is None or lon is None:
        return None
    return Place(label=label, lat=lat, lon=lon, kind=kind)


def _routable_position(result: dict[str, Any]) -> tuple[float | None, float | None]:
    """Prefer the main entry point (where the property meets the road) over the center point."""
    for entry in result.get("entryPoints", []):
        if entry.get("type") == "main":
            return entry["position"]["lat"], entry["position"]["lon"]
    position = result.get("position", {})
    return position.get("lat"), position.get("lon")
