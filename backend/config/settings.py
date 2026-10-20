"""Django settings. All environment-specific values come from env vars (see ../.env.example)."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# The app stores nothing, so there are no models, no database and no auth.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES: dict = {}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        # Django's default of 300 entries is too small: a long trip caches ~250 weather grid points.
        "OPTIONS": {"MAX_ENTRIES": 20_000},
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    # Protects the shared TomTom daily quota from a single client hammering the API.
    "DEFAULT_THROTTLE_RATES": {"geocode": "120/min", "plan": "20/min", "heatmap": "20/min"},
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# External provider keys.
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")
# Optional: a paid Open-Meteo plan key. Empty means the free, keyless endpoint.
OPEN_METEO_API_KEY = os.environ.get("OPEN_METEO_API_KEY", "")
# Free tier: 600 locations/min, 5,000/hour, 10,000/day. We stay a little under each.
OPEN_METEO_FREE_LIMITS = {"per_minute": 550, "per_hour": 4_500, "per_day": 9_000}

# Weather map (heatmap): grid cells within this distance of any route, at most this many cells.
HEATMAP_CORRIDOR_KM = 50
HEATMAP_MAX_CELLS = int(os.environ.get("HEATMAP_MAX_CELLS", "250"))
