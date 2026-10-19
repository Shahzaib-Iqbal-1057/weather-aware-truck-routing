import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from trips.domain.types import Place, PlaceKind
from trips.providers.base import ProviderError
from trips.services import geocoding


class FakeGeocoder:
    def __init__(self, places=None, error=None):
        self.places = places or []
        self.error = error
        self.calls = 0

    def search(self, query, *, limit):
        self.calls += 1
        if self.error:
            raise self.error
        return self.places[:limit]


@pytest.fixture
def fake_geocoder(monkeypatch):
    fake = FakeGeocoder([Place(label="Denver, CO", lat=39.74, lon=-104.99, kind=PlaceKind.CITY)])
    monkeypatch.setattr(geocoding, "get_geocoder", lambda: fake)
    return fake


def get(query):
    return APIClient().get(reverse("geocode"), {"q": query})


def test_returns_places_with_time_zone(fake_geocoder):
    response = get("denv")

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "label": "Denver, CO",
                "lat": 39.74,
                "lon": -104.99,
                "kind": "city",
                "timezone": "America/Denver",
            }
        ]
    }


def test_repeated_queries_are_served_from_cache(fake_geocoder):
    get("denver")
    get("  Denver ")

    assert fake_geocoder.calls == 1


@pytest.mark.parametrize("query", ["", "de", "x" * 101])
def test_rejects_queries_of_invalid_length(fake_geocoder, query):
    response = get(query)

    assert response.status_code == 400
    assert fake_geocoder.calls == 0


def test_provider_failure_returns_bad_gateway(monkeypatch):
    monkeypatch.setattr(
        geocoding, "get_geocoder", lambda: FakeGeocoder(error=ProviderError("boom"))
    )

    response = get("denver")

    assert response.status_code == 502
    assert response.json() == {"detail": "Location search is temporarily unavailable."}
