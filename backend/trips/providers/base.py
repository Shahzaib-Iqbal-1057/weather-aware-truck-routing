from typing import Protocol

from trips.domain.types import Place


class ProviderError(Exception):
    """An external API failed or returned something unusable.

    Messages must never contain API keys or full request URLs.
    """


class Geocoder(Protocol):
    def search(self, query: str, *, limit: int) -> list[Place]:
        """Return up to `limit` US places matching a partial query, best match first."""
        ...
