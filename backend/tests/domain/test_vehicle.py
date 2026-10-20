import pytest

from trips.domain.vehicle import standard_semi

LB_TO_KG = 0.45359237


@pytest.mark.parametrize(
    ("cargo_lb", "gross_lb"),
    [(0, 35_000), (30_000, 65_000), (45_000, 80_000), (60_000, 80_000)],
)
def test_gross_weight_is_empty_truck_plus_cargo_capped_at_the_legal_limit(cargo_lb, gross_lb):
    assert standard_semi(cargo_lb).weight_kg == pytest.approx(gross_lb * LB_TO_KG)


def test_dimensions_are_rounded_up_so_limits_are_never_understated():
    semi = standard_semi(0)
    assert semi.height_m == 4.12  # 13 ft 6 in = 4.1148 m
    assert semi.width_m == 2.60  # 8 ft 6 in = 2.5908 m
    assert semi.length_m == 21.95  # 72 ft = 21.9456 m
    assert semi.axles == 5


def test_speed_is_capped_at_65_mph():
    assert standard_semi(0).max_speed_kmh == pytest.approx(65 * 1.609344)
