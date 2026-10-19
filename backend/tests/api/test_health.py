from django.urls import reverse
from rest_framework.test import APIClient


def test_health_returns_ok():
    response = APIClient().get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
