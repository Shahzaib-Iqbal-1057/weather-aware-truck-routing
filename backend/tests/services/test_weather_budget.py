import pytest

from trips.services.weather_budget import (
    WeatherAllowanceUsedUp,
    WeatherBudget,
    WeatherBudgetExceeded,
)


class Clock:
    def __init__(self, start=1_000_040.0):  # 1,000,020 is a whole minute, so this is 20 s in
        self.now = start
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def budget(clock, **limits):
    values = {"per_minute": 100, "per_hour": 1_000, "per_day": 2_000} | limits
    return WeatherBudget(**values, clock=clock, sleep=clock.sleep)


def test_requests_within_the_minute_go_straight_through():
    clock = Clock()
    b = budget(clock)
    b.acquire(60)
    b.acquire(40)
    assert clock.slept == []


def test_a_request_that_overflows_the_minute_waits_for_the_next_one():
    clock = Clock()
    b = budget(clock)
    b.acquire(80)
    b.acquire(30)
    assert len(clock.slept) == 1
    assert 40 < clock.slept[0] <= 41  # waits out the rest of the minute


def test_the_hourly_and_daily_allowances_are_refused_not_waited_for():
    clock = Clock()
    b = budget(clock, per_hour=150)
    b.acquire(100)
    clock.now += 60
    with pytest.raises(WeatherAllowanceUsedUp, match="hourly"):
        b.acquire(60)

    b = budget(Clock(), per_day=50, per_minute=100)
    with pytest.raises(WeatherAllowanceUsedUp, match="daily"):
        b.acquire(60)


def test_remaining_today_counts_down():
    b = budget(Clock())
    b.acquire(70)
    assert b.remaining_today() == 1_930


def test_oversized_requests_must_be_split():
    with pytest.raises(ValueError):
        budget(Clock()).acquire(101)


def test_gives_up_if_the_minute_never_frees_up_in_time():
    clock = Clock()
    b = WeatherBudget(
        per_minute=100, per_hour=1_000, per_day=2_000, max_wait_s=5, clock=clock, sleep=clock.sleep
    )
    b.acquire(100)
    with pytest.raises(WeatherBudgetExceeded, match="busy"):
        b.acquire(10)


def test_waiting_for_the_next_minute_does_not_block_other_requests():
    clock = Clock()
    b = budget(clock)
    locked_while_sleeping = []

    def sleep(seconds):
        locked_while_sleeping.append(b._lock.locked())
        clock.sleep(seconds)

    b._sleep = sleep
    b.acquire(80)
    b.acquire(30)

    assert locked_while_sleeping == [False]


def test_a_busy_minute_is_not_reported_as_a_used_up_allowance():
    clock = Clock()
    b = WeatherBudget(
        per_minute=100, per_hour=1_000, per_day=2_000, max_wait_s=5, clock=clock, sleep=clock.sleep
    )
    b.acquire(100)
    with pytest.raises(WeatherBudgetExceeded) as raised:
        b.acquire(10)
    assert not isinstance(raised.value, WeatherAllowanceUsedUp)
