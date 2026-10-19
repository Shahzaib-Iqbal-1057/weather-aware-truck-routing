import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from trips.api.serializers import (
    GeocodeQuerySerializer,
    PlaceSerializer,
    TripPlanRequestSerializer,
    TripSerializer,
)
from trips.providers.base import ProviderError
from trips.services.geocoding import search_places

logger = logging.getLogger(__name__)


class HealthView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class GeocodeView(APIView):
    """Autocomplete for origin/destination. Proxies TomTom so the API key stays on the server."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        query = GeocodeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            places = search_places(query.validated_data["q"])
        except ProviderError:
            logger.exception("Geocoding failed")
            return Response(
                {"detail": "Location search is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"results": PlaceSerializer(places, many=True).data})


class TripPlanView(APIView):
    """Stage 0: validate and normalize the trip. Later stages add routes, weather and risk."""

    def post(self, request: Request) -> Response:
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "trip": TripSerializer(serializer.validated_data["trip"]).data,
                "warnings": serializer.validated_data["warnings"],
            }
        )
