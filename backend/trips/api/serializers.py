from datetime import UTC, datetime

from django.utils import timezone
from rest_framework import serializers

from trips.domain.candidates import label_points
from trips.domain.geo import METERS_PER_MILE, LatLon, simplify
from trips.domain.risk import CheckpointRisk, RiskLevel
from trips.domain.risk_stretches import risk_stretches
from trips.domain.trip_request import (
    DEFAULT_SPACING_MI,
    TripRequest,
    TripValidationError,
    build_trip_request,
)
from trips.domain.types import Place, PlaceKind
from trips.domain.weather import HourlyWeather, describe_conditions
from trips.services.heatmap import Heatmap
from trips.services.plan_trip import PlannedRoute, TripPlan
from trips.services.timezones import timezone_at


class LocalDateTimeField(serializers.Field):
    """Wall-clock time without an offset, e.g. "2026-10-20T08:00", read in the origin's zone."""

    default_error_messages = {"invalid": "Use the format YYYY-MM-DDTHH:MM, without a time zone."}

    def to_internal_value(self, data: object) -> datetime:
        try:
            value = datetime.fromisoformat(str(data))
        except ValueError:
            self.fail("invalid")
        if value.tzinfo is not None:
            self.fail("invalid")
        return value.replace(second=0, microsecond=0)

    def to_representation(self, value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M")


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=300)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    kind = serializers.ChoiceField(choices=[kind.value for kind in PlaceKind], default="place")
    timezone = serializers.CharField(read_only=True, allow_null=True)

    def to_internal_value(self, data: object) -> Place:
        values = super().to_internal_value(data)
        return Place(
            label=values["label"], lat=values["lat"], lon=values["lon"], kind=values["kind"]
        )


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=100, trim_whitespace=True)


class TripPlanRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_local = LocalDateTimeField()
    cargo_weight_lb = serializers.IntegerField()
    spacing_mi = serializers.IntegerField(default=DEFAULT_SPACING_MI)

    def validate(self, attrs: dict) -> dict:
        origin, destination = attrs["origin"], attrs["destination"]
        try:
            trip, warnings = build_trip_request(
                **attrs,
                origin_timezone=timezone_at(origin.lat, origin.lon),
                destination_timezone=timezone_at(destination.lat, destination.lon),
                now=timezone.now(),
            )
        except TripValidationError as exc:
            raise serializers.ValidationError(exc.errors) from None
        return {"trip": trip, "warnings": warnings}


class TripSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_local = serializers.SerializerMethodField()
    departure_utc = serializers.DateTimeField()
    departure_timezone = serializers.CharField()
    departure_timezone_abbr = serializers.SerializerMethodField()
    cargo_weight_lb = serializers.IntegerField()
    spacing_mi = serializers.IntegerField()

    def get_departure_local(self, trip: TripRequest) -> str:
        return trip.departure_local.strftime("%Y-%m-%dT%H:%M")

    def get_departure_timezone_abbr(self, trip: TripRequest) -> str:
        return trip.departure_local.strftime("%Z")


# Display lines are simplified: a point that deviates less than this from the line is dropped.
# The full geometry stays on the server for checkpoint placement.
DISPLAY_TOLERANCE_M = 25.0


def serialize_plan(plan: TripPlan, warnings: list[str]) -> dict:
    """The planned trip for the browser. Routes are labelled A, B, C in order of arrival."""
    labels = label_points([planned.route for planned in plan.routes])
    index = plan.recommendation.route_index
    return {
        "trip": TripSerializer(plan.trip).data,
        "routes": [
            _serialize_route(planned, label)
            for planned, label in zip(plan.routes, labels, strict=True)
        ],
        "recommendation": {
            "route_id": plan.routes[index].id if index is not None else None,
            "reason": plan.recommendation.reason,
        },
        "weather_available": plan.weather_available,
        "notes": plan.notes,
        "warnings": warnings,
    }


def _serialize_route(planned: PlannedRoute, label: LatLon) -> dict:
    route, timeline, totals = planned.route, planned.timeline, planned.totals
    return {
        "id": planned.id,
        "distance_mi": round(route.length_m / METERS_PER_MILE, 1),
        "driving_time_s": round(timeline.driving_s),
        "trip_time_s": round(timeline.trip_s),  # door to door, including rest stops
        "arrival_utc": _utc(timeline.arrival),
        "totals": {
            "severe_mi": round(totals.severe_mi, 1),
            "high_mi": round(totals.high_mi, 1),
            "no_travel_mi": round(totals.no_travel_mi, 1),
            "unknown_mi": round(totals.unknown_mi, 1),
            "average_risk": (
                round(totals.average_risk, 3) if totals.average_risk is not None else None
            ),
        },
        "geometry": [_lon_lat(point) for point in simplify(route.points, DISPLAY_TOLERANCE_M)],
        # Where to put the route's map label: on road no other route shares.
        "label_position": _lon_lat(label),
        "checkpoints": [
            {
                "position": _lon_lat(checkpoint.position),
                "mile": round(checkpoint.mile, 1),
                "eta_utc": _utc(checkpoint.eta),
                "weather": _serialize_weather(weather),
                "risk": _serialize_risk(risk),
            }
            for checkpoint, weather, risk in zip(
                timeline.checkpoints, planned.weather, planned.risk, strict=True
            )
        ],
        # Moderate-or-worse road, drawn in risk colours over the route line.
        "risk_stretches": [
            {
                "level": stretch.level.key,
                "from_mi": round(stretch.from_mi, 1),
                "to_mi": round(stretch.to_mi, 1),
                "geometry": [
                    _lon_lat(point) for point in simplify(stretch.points, DISPLAY_TOLERANCE_M)
                ],
            }
            for stretch in risk_stretches(route, timeline, planned.risk)
        ],
        "rest_stops": [
            {
                "kind": stop.kind.value,
                "position": _lon_lat(stop.position),
                "mile": round(stop.mile, 1),
                "starts_utc": _utc(stop.starts),
                "ends_utc": _utc(stop.ends),
            }
            for stop in timeline.stops
        ],
    }


def _serialize_risk(risk: CheckpointRisk | None) -> dict:
    if risk is None:
        return {"level": "unknown", "reasons": ["No forecast for this place and hour"]}
    return {"level": risk.level.key, "reasons": risk.reasons}


def _serialize_weather(weather: HourlyWeather | None) -> dict | None:
    if weather is None:
        return None
    return {
        "forecast_hour_utc": _utc(weather.hour),
        # Already rounded once by the risk stage; shown exactly as classified.
        "wind_mph": weather.wind_mph,
        "gust_mph": weather.gust_mph,
        "rain_in_per_hr": weather.rain_in_per_hr,
        "snow_in_per_hr": weather.snow_in_per_hr,
        "temperature_f": round(weather.temperature_f)
        if weather.temperature_f is not None
        else None,
        "conditions": describe_conditions(weather.weather_code),
    }


def _lon_lat(point: LatLon) -> list[float]:
    """GeoJSON order: [lon, lat]."""
    lat, lon = point
    return [round(lon, 5), round(lat, 5)]


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# One character per hour: "0" Low … "4" No Travel, "-" no forecast.
_LEVEL_CODES = {level: str(int(level)) for level in RiskLevel}


def serialize_heatmap(heatmap: Heatmap) -> dict:
    """Only cells that ever reach Moderate or worse are sent: Low is drawn transparent."""
    shown = [
        cell
        for cell in heatmap.cells
        if any(level is not None and level >= RiskLevel.MODERATE for level in cell.levels)
    ]
    return {
        "start_utc": _utc(heatmap.start),
        "hours": len(heatmap.cells[0].levels) if heatmap.cells else 0,
        "cell_size_deg": heatmap.cell_deg,
        "cells_in_corridor": len(heatmap.cells),
        "cells": [
            {
                "center": _lon_lat(cell.center),
                "levels": "".join(
                    _LEVEL_CODES[level] if level is not None else "-" for level in cell.levels
                ),
            }
            for cell in shown
        ],
    }
