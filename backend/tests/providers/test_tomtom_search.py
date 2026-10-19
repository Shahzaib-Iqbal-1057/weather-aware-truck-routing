from unittest.mock import Mock

import pytest
import requests

from trips.domain.types import Place, PlaceKind
from trips.providers.base import ProviderError
from trips.providers.tomtom_search import TomTomGeocoder, parse_search_results

# Trimmed-down shapes of real TomTom Fuzzy Search results.
PAYLOAD = {
    "results": [
        {
            "type": "Geography",
            "entityType": "Municipality",
            "address": {"freeformAddress": "Dallas, TX"},
            "position": {"lat": 32.78, "lon": -96.80},
        },
        {
            "type": "Geography",
            "entityType": "CountrySubdivision",
            "address": {"freeformAddress": "TX"},
            "position": {"lat": 31.0, "lon": -99.0},
        },
        {
            "type": "POI",
            "poi": {"name": "Walmart Distribution Center"},
            "address": {"freeformAddress": "1201 SE Moberly Ln, Bentonville, AR 72712"},
            "position": {"lat": 36.36, "lon": -94.18},
            "entryPoints": [
                {"type": "minor", "position": {"lat": 36.35, "lon": -94.17}},
                {"type": "main", "position": {"lat": 36.361, "lon": -94.181}},
            ],
        },
        {
            "type": "Point Address",
            "address": {"freeformAddress": "100 Main St, Dallas, TX 75201"},
            "position": {"lat": 32.78, "lon": -96.79},
        },
        {
            "type": "Geography",
            "entityType": "Municipality",
            "address": {"freeformAddress": "Dallas, TX"},
            "position": {"lat": 32.78, "lon": -96.80},
        },
    ]
}


def test_parse_maps_result_types_and_drops_unusable_ones():
    places = parse_search_results(PAYLOAD)

    assert places == [
        Place(label="Dallas, TX", lat=32.78, lon=-96.80, kind=PlaceKind.CITY),
        Place(
            label="Walmart Distribution Center, 1201 SE Moberly Ln, Bentonville, AR 72712",
            lat=36.361,
            lon=-94.181,
            kind=PlaceKind.PLACE,
        ),
        Place(label="100 Main St, Dallas, TX 75201", lat=32.78, lon=-96.79, kind=PlaceKind.ADDRESS),
    ]


def test_parse_handles_empty_payload():
    assert parse_search_results({}) == []


def fake_session(*, status_code=200, payload=None, error=None) -> Mock:
    session = Mock()
    if error:
        session.get.side_effect = error
    else:
        session.get.return_value = Mock(status_code=status_code, json=Mock(return_value=payload))
    return session


def test_search_requests_us_typeahead_results():
    session = fake_session(payload=PAYLOAD)

    places = TomTomGeocoder("secret-key", session=session).search("dallas tx", limit=2)

    assert len(places) == 2
    url = session.get.call_args.args[0]
    params = session.get.call_args.kwargs["params"]
    assert url.endswith("/search/dallas%20tx.json")
    assert params["countrySet"] == "US"
    assert params["typeahead"] == "true"


def test_search_without_api_key_fails_clearly():
    with pytest.raises(ProviderError, match="not configured"):
        TomTomGeocoder("").search("dallas", limit=5)


def test_search_raises_on_http_error_without_leaking_key():
    session = fake_session(status_code=403)

    with pytest.raises(ProviderError) as exc_info:
        TomTomGeocoder("secret-key", session=session).search("dallas", limit=5)

    assert "403" in str(exc_info.value)
    assert "secret-key" not in str(exc_info.value)


def test_search_raises_on_network_error():
    session = fake_session(error=requests.ConnectionError("https://api.tomtom.com/?key=secret-key"))

    with pytest.raises(ProviderError) as exc_info:
        TomTomGeocoder("secret-key", session=session).search("dallas", limit=5)

    assert "secret-key" not in str(exc_info.value)
