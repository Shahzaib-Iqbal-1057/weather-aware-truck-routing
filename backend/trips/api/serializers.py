from datetime import datetime

from django.utils import timezone
from rest_framework import serializers

from trips.domain.trip_request import (
    DEFAULT_SPACING_MI,
    TripRequest,
    TripValidationError,
    build_trip_request,
)
from trips.domain.types import Place, PlaceKind


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
    weight_lb = serializers.IntegerField()
    spacing_mi = serializers.IntegerField(default=DEFAULT_SPACING_MI)

    def validate(self, attrs: dict) -> dict:
        try:
            trip, warnings = build_trip_request(**attrs, now=timezone.now())
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
    weight_lb = serializers.IntegerField()
    spacing_mi = serializers.IntegerField()

    def get_departure_local(self, trip: TripRequest) -> str:
        return trip.departure_local.strftime("%Y-%m-%dT%H:%M")

    def get_departure_timezone_abbr(self, trip: TripRequest) -> str:
        return trip.departure_local.strftime("%Z")
