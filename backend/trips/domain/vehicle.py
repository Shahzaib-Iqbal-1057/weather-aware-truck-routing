"""The truck we route for. The user only gives weight, so dimensions assume a standard US semi."""

from dataclasses import dataclass

KG_PER_LB = 0.45359237


@dataclass(frozen=True)
class VehicleProfile:
    weight_kg: float
    height_m: float
    width_m: float
    length_m: float
    axles: int


# Tractor with a 53 ft trailer: 13 ft 6 in tall, 8 ft 6 in wide, ~72 ft long, 5 axles.
# Sending dimensions makes the router respect low bridges and length restrictions.
STANDARD_SEMI_HEIGHT_M = 4.11
STANDARD_SEMI_WIDTH_M = 2.59
STANDARD_SEMI_LENGTH_M = 21.9
STANDARD_SEMI_AXLES = 5


def standard_semi(weight_lb: int) -> VehicleProfile:
    return VehicleProfile(
        weight_kg=weight_lb * KG_PER_LB,
        height_m=STANDARD_SEMI_HEIGHT_M,
        width_m=STANDARD_SEMI_WIDTH_M,
        length_m=STANDARD_SEMI_LENGTH_M,
        axles=STANDARD_SEMI_AXLES,
    )
