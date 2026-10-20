"""The truck we route for. The user only gives weight, so the rest assumes a standard US semi."""

from dataclasses import dataclass

KG_PER_LB = 0.45359237
KMH_PER_MPH = 1.609344


@dataclass(frozen=True)
class VehicleProfile:
    weight_kg: float
    height_m: float
    width_m: float
    length_m: float
    axles: int
    max_speed_kmh: float


# Tractor with a 53 ft trailer: 13 ft 6 in tall, 8 ft 6 in wide, ~72 ft long, 5 axles.
# Sending dimensions makes the router respect low bridges and length restrictions.
STANDARD_SEMI_HEIGHT_M = 4.11
STANDARD_SEMI_WIDTH_M = 2.59
STANDARD_SEMI_LENGTH_M = 21.9
STANDARD_SEMI_AXLES = 5
# There is no federal truck speed cap (a 65 mph limiter rule was withdrawn in July 2025), but most
# large fleets govern trucks, commonly at 65 mph. Capping makes ETAs conservative (later).
STANDARD_SEMI_MAX_SPEED_MPH = 65


def standard_semi(weight_lb: int) -> VehicleProfile:
    return VehicleProfile(
        weight_kg=weight_lb * KG_PER_LB,
        height_m=STANDARD_SEMI_HEIGHT_M,
        width_m=STANDARD_SEMI_WIDTH_M,
        length_m=STANDARD_SEMI_LENGTH_M,
        axles=STANDARD_SEMI_AXLES,
        max_speed_kmh=STANDARD_SEMI_MAX_SPEED_MPH * KMH_PER_MPH,
    )
