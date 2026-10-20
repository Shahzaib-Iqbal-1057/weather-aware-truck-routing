"""Keeps the app inside Open-Meteo's free-tier limits, across all users.

The free tier allows 600 locations per minute, 5,000 per hour and 10,000 per day, and every
location in a batched request counts. All weather fetches pass through one budget: a request that
would overflow the current minute waits for the next one; one that would overflow the hour or day
is refused, and the app shows weather as unavailable instead of failing outright.

Counts are kept in this process's memory, so the app runs as a single server process. With a paid
key (no limits) there is no budget at all.
"""

import threading
import time
from collections.abc import Callable

from django.conf import settings

from trips.providers.base import ProviderError

MINUTE, HOUR, DAY = 60, 3600, 86_400


class WeatherBudgetExceeded(ProviderError):
    """The hourly or daily allowance is used up (or the minute did not free up in time)."""


class WeatherBudget:
    def __init__(
        self,
        *,
        per_minute: int,
        per_hour: int,
        per_day: int,
        max_wait_s: float = 65,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.limits = {MINUTE: per_minute, HOUR: per_hour, DAY: per_day}
        self.max_wait_s = max_wait_s
        self._clock, self._sleep = clock, sleep
        self._used: dict[tuple[int, int], int] = {}  # (window length, window number) → locations
        self._lock = threading.Lock()

    @property
    def batch_limit(self) -> int:
        """Most locations one request may ask for and still fit in a minute."""
        return self.limits[MINUTE]

    def acquire(self, locations: int) -> None:
        """Reserve `locations`, waiting for the next minute if needed."""
        if locations > self.batch_limit:
            raise ValueError(f"Split requests to at most {self.batch_limit} locations.")
        waited = 0.0
        with self._lock:
            while True:
                now = self._clock()
                for window in (DAY, HOUR):
                    if self._count(window, now) + locations > self.limits[window]:
                        period = "daily" if window == DAY else "hourly"
                        raise WeatherBudgetExceeded(f"The {period} weather allowance is used up.")
                if self._count(MINUTE, now) + locations <= self.limits[MINUTE]:
                    for window in self.limits:
                        key = (window, int(now // window))
                        self._used[key] = self._used.get(key, 0) + locations
                    self._forget_old(now)
                    return
                wait = MINUTE - now % MINUTE + 0.5
                if waited + wait > self.max_wait_s:
                    raise WeatherBudgetExceeded("The weather service is busy; try again shortly.")
                self._sleep(wait)
                waited += wait

    def remaining_today(self) -> int:
        with self._lock:
            return self.limits[DAY] - self._count(DAY, self._clock())

    def _count(self, window: int, now: float) -> int:
        return self._used.get((window, int(now // window)), 0)

    def _forget_old(self, now: float) -> None:
        current = {(window, int(now // window)) for window in self.limits}
        for key in [key for key in self._used if key not in current]:
            del self._used[key]


_budget: WeatherBudget | None = None


def get_budget() -> WeatherBudget | None:
    """The shared budget, or None with a paid key (no limits)."""
    global _budget
    if settings.OPEN_METEO_API_KEY:
        return None
    if _budget is None:
        _budget = WeatherBudget(**settings.OPEN_METEO_FREE_LIMITS)
    return _budget
