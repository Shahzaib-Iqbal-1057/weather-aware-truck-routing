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
    serialize_plan,
)
from trips.providers.base import NoRouteError, ProviderError
from trips.services.geocoding import search_places
from trips.services.plan_trip import plan_trip

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
    """Validate the trip, then run the pipeline: routes, checkpoints and ETAs, weather."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "plan"

    def post(self, request: Request) -> Response:
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            plan = plan_trip(serializer.validated_data["trip"])
        except NoRouteError:
            return Response(
                {"detail": "No truck route exists between these places."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except ProviderError:
            logger.exception("Route planning failed")
            return Response(
                {"detail": "Route planning is temporarily unavailable."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(serialize_plan(plan, serializer.validated_data["warnings"]))
