from datetime import UTC, datetime, timedelta, timezone

import pytest

from trips.domain.weather import describe_conditions, forecast_hour, grid_point


@pytest.mark.parametrize(
    ("eta", "expected"),
    [
        (datetime(2026, 10, 20, 9, 40, tzinfo=UTC), datetime(2026, 10, 20, 10, 0, tzinfo=UTC)),
        (datetime(2026, 10, 20, 9, 0, 30, tzinfo=UTC), datetime(2026, 10, 20, 10, 0, tzinfo=UTC)),
        (datetime(2026, 10, 20, 10, 0, tzinfo=UTC), datetime(2026, 10, 20, 10, 0, tzinfo=UTC)),
        (datetime(2026, 10, 20, 23, 5, tzinfo=UTC), datetime(2026, 10, 21, 0, 0, tzinfo=UTC)),
    ],
)
def test_forecast_hour_is_the_record_covering_the_eta(eta, expected):
    assert forecast_hour(eta) == expected


def test_forecast_hour_is_in_utc_whatever_the_input_zone():
    cdt = timezone(timedelta(hours=-5))
    assert forecast_hour(datetime(2026, 10, 20, 4, 40, tzinfo=cdt)) == datetime(
        2026, 10, 20, 10, 0, tzinfo=UTC
    )


def test_grid_point_snaps_to_five_hundredths_of_a_degree():
    assert grid_point((35.4672, -97.5164)) == (35.45, -97.5)
    assert grid_point((35.4751, -97.5251)) == (35.5, -97.55)


def test_nearby_points_on_the_same_road_share_a_grid_point():
    assert grid_point((35.4672, -97.5164)) == grid_point((35.4669, -97.5170))


def test_conditions_are_described_from_wmo_codes():
    assert describe_conditions(95) == "Thunderstorm"
    assert describe_conditions(None) is None
    assert describe_conditions(12345) is None
