from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from trips.domain.geo import BoundingBox
from trips.domain.types import Place
from trips.domain.vehicle import standard_semi
from trips.providers.base import NoRouteError, ProviderError
from trips.providers.tomtom_routing import TomTomRouter, parse_routes

ORIGIN = Place(label="Denver, CO", lat=39.7392, lon=-104.9903)
DESTINATION = Place(label="Colorado Springs, CO", lat=38.8339, lon=-104.8214)
DEPART = datetime(2026, 10, 20, 14, 0, tzinfo=UTC)

# Trimmed shape of a real Calculate Route response.
PAYLOAD = {
    "routes": [
        {
            "summary": {
                "lengthInMeters": 3000,
                "travelTimeInSeconds": 300,
                "trafficDelayInSeconds": 20,
            },
            "legs": [
                {
                    "points": [
                        {"latitude": 39.000, "longitude": -105.0},
                        {"latitude": 39.009, "longitude": -105.0},
                        {"latitude": 39.018, "longitude": -105.0},
                        {"latitude": 39.027, "longitude": -105.0},
                    ]
                }
            ],
            "progress": [
                {"pointIndex": 0, "travelTimeInSeconds": 0, "distanceInMeters": 0},
                {"pointIndex": 2, "travelTimeInSeconds": 240, "distanceInMeters": 2000},
                {"pointIndex": 3, "travelTimeInSeconds": 300, "distanceInMeters": 3000},
            ],
        }
    ]
}


def test_parse_interpolates_distance_and_time_between_progress_points():
    [route] = parse_routes(PAYLOAD)

    assert len(route.points) == 4
    assert route.distances_m == pytest.approx([0, 1000, 2000, 3000], abs=1)
    # Point 1 is halfway (by distance) between progress points 0 and 2.
    assert route.times_s == pytest.approx([0, 120, 240, 300], abs=1)
    assert route.length_m == 3000
    assert route.travel_time_s == 300
    assert route.traffic_delay_s == 20


def test_parse_joins_legs_without_repeating_the_shared_point():
    payload = {
        "routes": [
            {
                "summary": {"lengthInMeters": 2000, "travelTimeInSeconds": 200},
                "legs": [
                    {
                        "points": [
                            {"latitude": 39.0, "longitude": -105.0},
                            {"latitude": 39.009, "longitude": -105.0},
                        ]
                    },
                    {
                        "points": [
                            {"latitude": 39.009, "longitude": -105.0},
                            {"latitude": 39.018, "longitude": -105.0},
                        ]
                    },
                ],
            }
        ]
    }

    [route] = parse_routes(payload)

    assert len(route.points) == 3
    assert route.times_s[-1] == 200


def fake_session(*, status_code=200, payload=None, error=None) -> Mock:
    session = Mock()
    response = Mock(status_code=status_code, json=Mock(return_value=payload or {}))
    for method in (session.get, session.post):
        if error:
            method.side_effect = error
        else:
            method.return_value = response
    return session


def route(router, **kwargs):
    defaults = {"depart_at": DEPART, "vehicle": standard_semi(65_000), "max_alternatives": 3}
    return router.routes(ORIGIN, DESTINATION, **(defaults | kwargs))


def test_requests_a_truck_route_with_weight_dimensions_and_departure():
    session = fake_session(payload=PAYLOAD)

    routes = route(TomTomRouter("secret-key", session=session))

    assert len(routes) == 1
    url = session.get.call_args.args[0]
    params = dict(session.get.call_args.kwargs["params"])
    assert url.endswith("/calculateRoute/39.7392,-104.9903:38.8339,-104.8214/json")
    assert params["travelMode"] == "truck"
    assert params["vehicleCommercial"] == "true"
    assert params["vehicleWeight"] == 29_484  # 65,000 lb in kg
    assert params["vehicleHeight"] == 4.11
    assert params["vehicleNumberOfAxles"] == 5
    assert params["departAt"] == "2026-10-20T14:00:00Z"
    assert params["maxAlternatives"] == 3
    extended = [
        v for k, v in session.get.call_args.kwargs["params"] if k == "extendedRouteRepresentation"
    ]
    assert set(extended) == {"distance", "travelTime"}


def test_caps_alternatives_at_the_api_maximum():
    session = fake_session(payload=PAYLOAD)
    route(TomTomRouter("secret-key", session=session), max_alternatives=9)
    assert dict(session.get.call_args.kwargs["params"])["maxAlternatives"] == 5


def test_sends_avoid_areas_in_a_post_body():
    session = fake_session(payload=PAYLOAD)
    box = BoundingBox(south=39.0, west=-105.5, north=39.5, east=-104.5)

    route(TomTomRouter("secret-key", session=session), avoid_areas=[box])

    session.get.assert_not_called()
    body = session.post.call_args.kwargs["json"]
    assert body == {
        "avoidAreas": {
            "rectangles": [
                {
                    "southWestCorner": {"latitude": 39.0, "longitude": -105.5},
                    "northEastCorner": {"latitude": 39.5, "longitude": -104.5},
                }
            ]
        }
    }


def test_no_route_found_raises_no_route_error():
    payload = {"detailedError": {"code": "NO_ROUTE_FOUND", "message": "No valid route found"}}
    session = fake_session(status_code=400, payload=payload)

    with pytest.raises(NoRouteError):
        route(TomTomRouter("secret-key", session=session))


def test_other_failures_raise_provider_error_without_leaking_key():
    session = fake_session(status_code=500)

    with pytest.raises(ProviderError) as exc_info:
        route(TomTomRouter("secret-key", session=session))

    assert not isinstance(exc_info.value, NoRouteError)
    assert "secret-key" not in str(exc_info.value)


def test_network_errors_raise_provider_error_without_leaking_key():
    session = fake_session(error=requests.Timeout("https://api.tomtom.com/?key=secret-key"))

    with pytest.raises(ProviderError) as exc_info:
        route(TomTomRouter("secret-key", session=session))

    assert "secret-key" not in str(exc_info.value)


def test_missing_api_key_fails_clearly():
    with pytest.raises(ProviderError, match="not configured"):
        route(TomTomRouter(""))
