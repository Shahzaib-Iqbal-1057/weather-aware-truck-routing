from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
import requests

from trips.providers.base import ProviderError
from trips.providers.open_meteo import FREE_URL, PAID_URL, OpenMeteoWeather, parse_hourly

START = datetime(2026, 10, 20, 10, tzinfo=UTC)
END = datetime(2026, 10, 20, 12, tzinfo=UTC)
T10 = int(START.timestamp())


def location(**hourly_overrides):
    hourly = {
        "time": [T10, T10 + 3600],
        "wind_speed_10m": [18.4, 40.0],
        "wind_gusts_10m": [31.2, 55.0],
        "rain": [0.10, 0.0],
        "showers": [0.05, 0.0],
        "snowfall": [0.0, 1.2],
        "temperature_2m": [54.0, 30.0],
        "weather_code": [61, 73],
    } | hourly_overrides
    return {"latitude": 35.45, "longitude": -97.5, "hourly": hourly}


def test_parse_adds_showers_to_rain_and_keeps_units():
    first, second = parse_hourly(location())

    assert first.hour == START
    assert first.wind_mph == 18.4
    assert first.gust_mph == 31.2
    assert first.rain_in_per_hr == pytest.approx(0.15)
    assert first.weather_code == 61
    assert second.snow_in_per_hr == 1.2


def test_parse_skips_hours_with_missing_risk_values_so_they_read_as_unknown():
    records = parse_hourly(location(wind_speed_10m=[None, 40.0]))
    assert [r.wind_mph for r in records] == [40.0]


def test_parse_tolerates_missing_display_values():
    [first, _] = parse_hourly(location(temperature_2m=[None, 30.0], weather_code=[None, 73]))
    assert first.temperature_f is None
    assert first.weather_code is None


def fake_session(*responses) -> Mock:
    session = Mock()
    session.get.side_effect = list(responses)
    return session


def ok(payload) -> Mock:
    return Mock(status_code=200, json=Mock(return_value=payload))


def test_requests_hourly_weather_in_risk_table_units_from_the_free_endpoint():
    session = fake_session(ok([location(), location()]))
    points = [(35.45, -97.5), (35.5, -97.55)]

    forecasts = OpenMeteoWeather(session=session).hourly(points, start=START, end=END)

    assert set(forecasts) == set(points)
    url, params = session.get.call_args.args[0], session.get.call_args.kwargs["params"]
    assert url == FREE_URL
    assert "apikey" not in params
    assert params["latitude"] == "35.4500,35.5000"
    assert params["longitude"] == "-97.5000,-97.5500"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert (params["start_hour"], params["end_hour"]) == ("2026-10-20T10:00", "2026-10-20T12:00")
    assert "showers" in params["hourly"].split(",")


def test_uses_the_paid_endpoint_when_a_key_is_set():
    session = fake_session(ok(location()))

    OpenMeteoWeather("paid-key", session=session).hourly([(35.45, -97.5)], start=START, end=END)

    assert session.get.call_args.args[0] == PAID_URL
    assert session.get.call_args.kwargs["params"]["apikey"] == "paid-key"


def test_single_location_response_is_accepted():
    session = fake_session(ok(location()))  # one location comes back as an object, not a list
    forecasts = OpenMeteoWeather(session=session).hourly([(35.45, -97.5)], start=START, end=END)
    assert len(forecasts[(35.45, -97.5)]) == 2


def test_many_points_are_sent_in_batches():
    points = [(30 + i * 0.05, -97.5) for i in range(250)]
    session = fake_session(ok([location()] * 100), ok([location()] * 100), ok([location()] * 50))

    forecasts = OpenMeteoWeather(session=session).hourly(points, start=START, end=END)

    assert session.get.call_count == 3
    assert len(forecasts) == 250


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (Mock(status_code=429), "rate limit"),
        (Mock(status_code=500), "HTTP 500"),
        (ok([location(), location()]), "different number"),
    ],
)
def test_failures_raise_provider_error(response, message):
    session = fake_session(response)
    with pytest.raises(ProviderError, match=message):
        OpenMeteoWeather(session=session).hourly([(35.45, -97.5)], start=START, end=END)


def test_network_errors_do_not_leak_the_key():
    session = fake_session(requests.ConnectionError("https://customer-api?apikey=paid-key"))
    with pytest.raises(ProviderError) as exc_info:
        OpenMeteoWeather("paid-key", session=session).hourly([(35.45, -97.5)], start=START, end=END)
    assert "paid-key" not in str(exc_info.value)
