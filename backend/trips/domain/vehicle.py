"""The truck we route for. The user only gives cargo weight, so the rest assumes a standard US
tractor with a 53 ft dry-van trailer."""

from dataclasses import dataclass
from math import ceil

KG_PER_LB = 0.45359237
KMH_PER_MPH = 1.609344
METERS_PER_FOOT = 0.3048

# Tractor + empty 53 ft trailer. Gross weight = this + cargo, up to the 80,000 lb federal limit.
STANDARD_SEMI_EMPTY_WEIGHT_LB = 35_000
LEGAL_GROSS_WEIGHT_LB = 80_000

# 13 ft 6 in tall, 8 ft 6 in wide, ~72 ft long, 5 axles. Sending dimensions makes the router
# respect low bridges and length restrictions.
STANDARD_SEMI_HEIGHT_FT = 13.5
STANDARD_SEMI_WIDTH_FT = 8.5
STANDARD_SEMI_LENGTH_FT = 72
STANDARD_SEMI_AXLES = 5

# There is no federal truck speed cap (a 65 mph limiter rule was withdrawn in July 2025), but most
# large fleets govern trucks, commonly at 65 mph. Capping makes ETAs conservative (later).
STANDARD_SEMI_MAX_SPEED_MPH = 65


@dataclass(frozen=True)
class VehicleProfile:
    weight_kg: float  # gross: truck + cargo
    height_m: float
    width_m: float
    length_m: float
    axles: int
    max_speed_kmh: float


def standard_semi(cargo_weight_lb: int) -> VehicleProfile:
    gross_lb = min(STANDARD_SEMI_EMPTY_WEIGHT_LB + cargo_weight_lb, LEGAL_GROSS_WEIGHT_LB)
    return VehicleProfile(
        weight_kg=gross_lb * KG_PER_LB,
        height_m=_feet_to_meters_rounded_up(STANDARD_SEMI_HEIGHT_FT),
        width_m=_feet_to_meters_rounded_up(STANDARD_SEMI_WIDTH_FT),
        length_m=_feet_to_meters_rounded_up(STANDARD_SEMI_LENGTH_FT),
        axles=STANDARD_SEMI_AXLES,
        max_speed_kmh=STANDARD_SEMI_MAX_SPEED_MPH * KMH_PER_MPH,
    )


def _feet_to_meters_rounded_up(feet: float) -> float:
    """To the next whole cm, so a bridge exactly at the truck's height is never treated as clear."""
    return ceil(feet * METERS_PER_FOOT * 100) / 100
