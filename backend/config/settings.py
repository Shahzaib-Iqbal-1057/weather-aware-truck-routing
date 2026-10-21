"""Django settings. All environment-specific values come from env vars (see ../.env.example)."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# Set by the Docker image: the deployed app, behind Fly.io's HTTPS proxy.
PRODUCTION = env_bool("DJANGO_PRODUCTION", default=False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
if PRODUCTION and SECRET_KEY in {"", "dev-only-insecure-key", "change-me"}:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a long random value in production.")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

if PRODUCTION:
    # The proxy terminates HTTPS and says so in this header; trust it only in production.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The app stores nothing, so there are no models, no database and no auth.
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves the built React app (see FRONTEND_DIST) before any URL routing.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
    # Candidate routes keep their full geometry (a long trip's three routes are ~2 MB), so they get
    # their own store with a small cap: memory stays bounded however many trips are planned.
    "routes": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "routes",
        "OPTIONS": {"MAX_ENTRIES": 50},
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    # Protects the shared TomTom daily quota from a single client hammering the API.
    "DEFAULT_THROTTLE_RATES": {"geocode": "120/min", "plan": "20/min", "heatmap": "20/min"},
    # Number of trusted reverse proxies in front of the app. Throttles identify clients by the
    # address the last trusted proxy saw; with 0 they use the socket address, so a client can't
    # dodge the limits by sending its own X-Forwarded-For header.
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "0")),
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"

# One deployable service: Django also serves the React build (index.html at "/", hashed bundles
# under /assets/). Locally the Vite dev server does this instead, so it is unset there.
FRONTEND_DIST = os.environ.get("FRONTEND_DIST")
if FRONTEND_DIST:
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True


def _is_hashed_bundle(path: str, url: str) -> bool:
    """Vite puts a content hash in every file name under /assets/, so they can be cached forever."""
    return url.startswith("/assets/")


WHITENOISE_IMMUTABLE_FILE_TEST = _is_hashed_bundle
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
