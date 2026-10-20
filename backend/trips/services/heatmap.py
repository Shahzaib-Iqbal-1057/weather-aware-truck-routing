"""Stage 8: the weather map, i.e. risk in every corridor cell for each of the 48 hours after
departure. Uses the trip's cargo, so it shows the same levels as the checkpoints."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings

from trips.domain.geo import LatLon
from trips.domain.heatmap import corridor_cells
from trips.domain.risk import RiskLevel, classify, rounded_for_rules
from trips.domain.trip_request import TripRequest
from trips.domain.weather import forecast_hour
from trips.providers.base import RoutingProvider, WeatherProvider
from trips.services.plan_trip import trip_routes
from trips.services.weather import hourly_records
from trips.services.weather_budget import get_budget

HOURS = 48
# When less than this many days' worth of the cap is left in today's free allowance, use a quarter
# of the cells (one size coarser), so the map keeps working instead of exhausting the allowance.
LOW_DAILY_BUDGET_MAPS = 4


@dataclass(frozen=True)
class HeatmapCell:
    center: LatLon
    levels: list[RiskLevel | None]  # one per hour from `start`; None = no forecast


@dataclass(frozen=True)
class Heatmap:
    cell_deg: float
    start: datetime  # forecast hour covering the departure
    cells: list[HeatmapCell]


def build_heatmap(
    trip: TripRequest,
    *,
    router: RoutingProvider | None = None,
    weather: WeatherProvider | None = None,
) -> Heatmap:
    max_cells = settings.HEATMAP_MAX_CELLS
    budget = get_budget()
    if budget is not None and budget.remaining_today() < LOW_DAILY_BUDGET_MAPS * max_cells:
        max_cells //= 4

    routes = trip_routes(trip, router=router)
    cell_deg, centers = corridor_cells(routes, settings.HEATMAP_CORRIDOR_KM, max_cells)
    start = forecast_hour(trip.departure_utc)
    hours = [start + timedelta(hours=h) for h in range(HOURS)]

    records = hourly_records(
        {center: set(hours) for center in centers},
        cache_name=f"heatmap{cell_deg}",
        provider=weather,
    )
    cells = []
    for center in centers:
        levels = []
        for hour in hours:
            forecast = records[center].get(hour)
            levels.append(
                classify(rounded_for_rules(forecast), trip.cargo_weight_lb).level
                if forecast is not None
                else None
            )
        cells.append(HeatmapCell(center, levels))
    return Heatmap(cell_deg=cell_deg, start=start, cells=cells)
