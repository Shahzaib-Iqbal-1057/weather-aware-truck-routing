"""Stage 4: risk level at each checkpoint, from the brief's risk table and load rules.

Boundaries: a value exactly on a shared edge takes the more severe level (rain 0.25 in/hr is High,
wind 35.0 mph is High). No Travel follows the table's own wording: wind ">= 55" (55.0 is No
Travel), rain "> 1.00" and snow "> 3.0" (1.00 and 3.0 are still Severe). Load rules apply to
sustained wind and cargo weight; "> 30,000 lb" means exactly 30,000 does not trigger them.

Gust safeguard (our addition, not in the brief): gusts of 55 mph or more raise the wind level to at
least High. Gusts are what push high-sided trucks over, but they are bursts, so they raise the
level to High rather than straight to No Travel.

Values are classified exactly as rounded for display (see `rounded_for_rules`), so the number on
screen always agrees with the level next to it.
"""

from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum

from trips.domain.weather import HourlyWeather


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

    @property
    def key(self) -> str:
        return self.name.lower()


# Lower bound of each level (inclusive) from Moderate up to Severe.
WIND_MPH = {RiskLevel.MODERATE: 25.0, RiskLevel.HIGH: 35.0, RiskLevel.SEVERE: 45.0}
RAIN_IN_PER_HR = {RiskLevel.MODERATE: 0.10, RiskLevel.HIGH: 0.25, RiskLevel.SEVERE: 0.50}
SNOW_IN_PER_HR = {RiskLevel.MODERATE: 0.5, RiskLevel.HIGH: 1.0, RiskLevel.SEVERE: 2.0}
WIND_NO_TRAVEL_FROM_MPH = 55.0  # ">= 55 mph"
RAIN_NO_TRAVEL_ABOVE = 1.00  # "> 1.00 in/hr"
SNOW_NO_TRAVEL_ABOVE = 3.0  # "> 3.0 in/hr"

# Load rules (sustained wind + cargo weight).
HEAVY_CARGO_NO_TRAVEL_ABOVE_LB = 30_000  # 45–54 mph + > 30,000 lb → No Travel
HEAVY_CARGO_SEVERE_ABOVE_LB = 40_000  # 35–44 mph + > 40,000 lb → Severe

GUST_HIGH_FROM_MPH = 55.0

WIND_DECIMALS = 1
PRECIPITATION_DECIMALS = 2


@dataclass(frozen=True)
class CheckpointRisk:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    reasons: list[str]  # what set the level, e.g. "Wind 47.2 mph with cargo over 30,000 lb"


def rounded_for_rules(weather: HourlyWeather) -> HourlyWeather:
    """Round once, half up, to the precision shown on screen; classification uses these values."""
    return replace(
        weather,
        wind_mph=_round_half_up(weather.wind_mph, WIND_DECIMALS),
        gust_mph=(
            _round_half_up(weather.gust_mph, WIND_DECIMALS)
            if weather.gust_mph is not None
            else None
        ),
        rain_in_per_hr=_round_half_up(weather.rain_in_per_hr, PRECIPITATION_DECIMALS),
        snow_in_per_hr=_round_half_up(weather.snow_in_per_hr, PRECIPITATION_DECIMALS),
    )


def classify(weather: HourlyWeather, cargo_weight_lb: int) -> CheckpointRisk:
    """Risk at one checkpoint. Expects values already passed through `rounded_for_rules`."""
    wind, wind_reason = _wind_level(weather, cargo_weight_lb)
    rain = _level(weather.rain_in_per_hr, RAIN_IN_PER_HR, no_travel=_above(RAIN_NO_TRAVEL_ABOVE))
    snow = _level(weather.snow_in_per_hr, SNOW_IN_PER_HR, no_travel=_above(SNOW_NO_TRAVEL_ABOVE))
    level = max(wind, rain, snow)

    reasons = []
    if level > RiskLevel.LOW:
        if wind == level:
            reasons.append(wind_reason)
        if rain == level:
            reasons.append(f"Rain {weather.rain_in_per_hr:.2f} in/hr")
        if snow == level:
            reasons.append(f"Snow {weather.snow_in_per_hr:.2f} in/hr")
    return CheckpointRisk(level=level, wind=wind, rain=rain, snow=snow, reasons=reasons)


def _wind_level(weather: HourlyWeather, cargo_weight_lb: int) -> tuple[RiskLevel, str]:
    sustained = weather.wind_mph
    level = _level(sustained, WIND_MPH, no_travel=lambda v: v >= WIND_NO_TRAVEL_FROM_MPH)
    reason = f"Wind {sustained:.1f} mph"

    # Load rules
    if level == RiskLevel.SEVERE and cargo_weight_lb > HEAVY_CARGO_NO_TRAVEL_ABOVE_LB:
        level = RiskLevel.NO_TRAVEL
        reason += f" with cargo over {HEAVY_CARGO_NO_TRAVEL_ABOVE_LB:,} lb"
    elif level == RiskLevel.HIGH and cargo_weight_lb > HEAVY_CARGO_SEVERE_ABOVE_LB:
        level = RiskLevel.SEVERE
        reason += f" with cargo over {HEAVY_CARGO_SEVERE_ABOVE_LB:,} lb"

    # Gust safeguard
    gust = weather.gust_mph
    if gust is not None and gust >= GUST_HIGH_FROM_MPH and level < RiskLevel.HIGH:
        level = RiskLevel.HIGH
        reason = f"Gusts {gust:.1f} mph"
    return level, reason


def _level(value: float, lower_bounds: dict[RiskLevel, float], *, no_travel) -> RiskLevel:
    if no_travel(value):
        return RiskLevel.NO_TRAVEL
    for level in (RiskLevel.SEVERE, RiskLevel.HIGH, RiskLevel.MODERATE):
        if value >= lower_bounds[level]:
            return level
    return RiskLevel.LOW


def _above(limit: float):
    return lambda value: value > limit


def _round_half_up(value: float, decimals: int) -> float:
    # Via the decimal string, so 24.95 rounds to 25.0 (binary floats would give 24.9).
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
