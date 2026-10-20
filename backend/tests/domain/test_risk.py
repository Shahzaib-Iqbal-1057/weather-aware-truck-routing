from datetime import UTC, datetime

import pytest

from trips.domain.risk import RiskLevel, classify, rounded_for_rules
from trips.domain.weather import HourlyWeather

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)
LIGHT_CARGO = 10_000


def weather(wind=0.0, gust=None, rain=0.0, snow=0.0):
    return HourlyWeather(
        hour=datetime(2026, 10, 20, 10, tzinfo=UTC),
        wind_mph=wind,
        gust_mph=gust,
        rain_in_per_hr=rain,
        snow_in_per_hr=snow,
        temperature_f=50.0,
        weather_code=0,
    )


@pytest.mark.parametrize(
    ("wind", "expected"),
    [
        (0, L), (24.9, L),
        (25.0, M), (34.9, M),
        (35.0, H), (44.9, H),
        (45.0, S), (54.9, S),
        (55.0, N), (70.0, N),
    ],
)  # fmt: skip
def test_wind_levels_and_boundaries(wind, expected):
    assert classify(weather(wind=wind), LIGHT_CARGO).wind == expected


@pytest.mark.parametrize(
    ("rain", "expected"),
    [
        (0.09, L),
        (0.10, M), (0.24, M),
        (0.25, H), (0.49, H),
        (0.50, S), (1.00, S),  # "> 1.00" is No Travel, so 1.00 is still Severe
        (1.01, N),
    ],
)  # fmt: skip
def test_rain_levels_and_boundaries(rain, expected):
    assert classify(weather(rain=rain), LIGHT_CARGO).rain == expected


@pytest.mark.parametrize(
    ("snow", "expected"),
    [
        (0.49, L),
        (0.50, M), (0.99, M),
        (1.00, H), (1.99, H),
        (2.00, S), (3.00, S),  # "> 3.0" is No Travel, so 3.0 is still Severe
        (3.01, N),
    ],
)  # fmt: skip
def test_snow_levels_and_boundaries(snow, expected):
    assert classify(weather(snow=snow), LIGHT_CARGO).snow == expected


@pytest.mark.parametrize(
    ("wind", "cargo", "expected"),
    [
        (47.0, 30_000, S),  # exactly 30,000 lb does not trigger "> 30,000"
        (47.0, 30_001, N),  # 45–54 mph + > 30,000 lb → No Travel
        (38.0, 40_000, H),  # exactly 40,000 lb does not trigger "> 40,000"
        (38.0, 40_001, S),  # 35–44 mph + > 40,000 lb → Severe
        (38.0, 35_000, H),  # heavy, but under 40,000: no load rule at 35–44 mph
        (30.0, 45_000, M),  # load rules start at 35 mph
        (55.0, 0, N),  # ≥ 55 mph is No Travel for any load
    ],
)
def test_load_rules_use_cargo_weight(wind, cargo, expected):
    assert classify(weather(wind=wind), cargo).wind == expected


@pytest.mark.parametrize(
    ("wind", "gust", "cargo", "expected"),
    [
        (20.0, 55.0, LIGHT_CARGO, H),  # gust safeguard raises Low to High
        (30.0, 54.9, LIGHT_CARGO, M),  # gust under 55: no change
        (38.0, 58.0, 42_000, S),  # already above High: gust never lowers it
        (48.0, 60.0, 35_000, N),  # load rule result stands
        (20.0, None, LIGHT_CARGO, L),  # missing gust is ignored
    ],
)
def test_gusts_of_55_mph_or_more_raise_wind_to_at_least_high(wind, gust, cargo, expected):
    assert classify(weather(wind=wind, gust=gust), cargo).wind == expected


def test_the_checkpoint_level_is_the_worst_condition_with_its_reasons():
    risk = classify(weather(wind=38.0, rain=0.30, snow=0.1), LIGHT_CARGO)

    assert (risk.wind, risk.rain, risk.snow, risk.level) == (H, H, L, H)
    assert risk.reasons == ["Wind 38.0 mph", "Rain 0.30 in/hr"]


def test_reasons_name_the_rule_that_applied():
    assert classify(weather(wind=47.2), 35_000).reasons == [
        "Wind 47.2 mph with cargo over 30,000 lb"
    ]
    assert classify(weather(wind=20.0, gust=56.4), LIGHT_CARGO).reasons == ["Gusts 56.4 mph"]


def test_calm_weather_is_low_with_no_reasons():
    risk = classify(weather(wind=8.0, gust=15.0), LIGHT_CARGO)
    assert (risk.level, risk.reasons) == (L, [])


def test_values_are_rounded_half_up_to_display_precision():
    rounded = rounded_for_rules(weather(wind=24.95, gust=54.95, rain=0.245, snow=0.495))

    assert (rounded.wind_mph, rounded.gust_mph) == (25.0, 55.0)
    assert (rounded.rain_in_per_hr, rounded.snow_in_per_hr) == (0.25, 0.5)


def test_rounding_then_classifying_agrees_with_what_is_shown():
    # 24.96 mph is shown as 25.0 mph, so it must be Moderate, not Low.
    shown = rounded_for_rules(weather(wind=24.96))
    assert shown.wind_mph == 25.0
    assert classify(shown, LIGHT_CARGO).wind == M


def test_levels_have_labels_and_keys():
    assert (N.label, N.key) == ("No Travel", "no_travel")
    assert (L.label, L.key) == ("Low", "low")
