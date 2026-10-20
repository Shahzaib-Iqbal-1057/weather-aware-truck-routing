"""Stage 6: recommend one route, in the brief's order of preference, and say why.

1. Routes with any No Travel checkpoint are not recommended (they are still shown).
2. Fewest Severe miles, then fewest High miles. Compared exactly: they already move in whole
   checkpoints, so equal counts are a genuine tie.
3. Lowest average risk. Averages almost never tie exactly, so a route counts as tied with the
   lowest when it is at most one checkpoint's worth higher: one checkpoint (spacing miles)
   changing one level, i.e. spacing ÷ the route's length. That is the smallest difference the
   sampling can detect; smaller differences flip with a 15-minute change of departure.
4. The fastest door-to-door of the routes still tied.

Travel time is also bounded upstream: no candidate is more than 25% slower than the fastest.
"""

from dataclasses import dataclass

from trips.domain.route_totals import RouteTotals

# Mile totals are sums of floats; differences below this are rounding, not a different count.
_EPSILON = 1e-6


@dataclass(frozen=True)
class Recommendation:
    route_index: int | None  # None: nothing can be recommended (see reason)
    reason: str


def recommend(totals: list[RouteTotals], ids: list[str], spacing_mi: float) -> Recommendation:
    if not any(t.has_forecast for t in totals):
        return Recommendation(
            None, "Weather is unavailable, so the routes can't be compared for safety."
        )

    dropped: dict[int, str] = {}  # route index → the step that ruled it out
    for i, t in enumerate(totals):
        if t.has_no_travel:
            dropped[i] = "no_travel"
        elif not t.has_forecast:
            dropped[i] = "unknown"
    remaining = [i for i in range(len(totals)) if i not in dropped]
    if not remaining:
        return Recommendation(
            None,
            "Every route crosses No Travel conditions, so none is recommended. "
            "Consider a later departure.",
        )

    def keep(step: str, is_best) -> None:
        nonlocal remaining
        for i in remaining:
            if not is_best(i):
                dropped[i] = step
        remaining = [i for i in remaining if i not in dropped]

    best_severe = min(totals[i].severe_mi for i in remaining)
    keep("severe", lambda i: totals[i].severe_mi <= best_severe + _EPSILON)
    best_high = min(totals[i].high_mi for i in remaining)
    keep("high", lambda i: totals[i].high_mi <= best_high + _EPSILON)
    best_average = min(totals[i].average_risk for i in remaining)
    keep(
        "average",
        lambda i: (
            totals[i].average_risk - best_average <= spacing_mi / totals[i].length_mi + _EPSILON
        ),
    )
    winner = min(remaining, key=lambda i: totals[i].trip_s)
    for i in remaining:
        if i != winner:
            dropped[i] = "time"

    return Recommendation(winner, _reason(winner, dropped, totals, ids))


def _reason(winner: int, dropped: dict[int, str], totals: list[RouteTotals], ids: list[str]) -> str:
    """Explain the pick against the most tempting alternative: the fastest route."""
    w, name = totals[winner], f"Route {ids[winner]}"
    note = f" No forecast for {w.unknown_mi:.0f} mi of it." if w.unknown_mi >= 1 else ""
    if len(totals) == 1:
        return f"{name}: the only truck route for this trip.{note}"

    fastest = min(range(len(totals)), key=lambda i: totals[i].trip_s)
    if fastest == winner:
        if all(step == "time" for step in dropped.values()):
            return (
                f"{name}: weather risk is practically the same on every route, "
                f"and {ids[winner]} is the fastest.{note}"
            )
        return f"{name}: the fastest route, and it has the least weather risk.{note}"

    other, rival = totals[fastest], ids[fastest]
    slower = f"{_duration(w.trip_s - other.trip_s)} slower than {rival}"
    step = dropped[fastest]
    if step == "no_travel":
        why = f"avoids the No Travel conditions on {rival}"
    elif step == "unknown":
        why = f"{rival} has no forecast to compare"
    elif step == "severe":
        why = f"fewer Severe miles than {rival} ({w.severe_mi:.0f} vs {other.severe_mi:.0f})"
    elif step == "high":
        why = (
            f"as few Severe miles as {rival} and fewer High miles "
            f"({w.high_mi:.0f} vs {other.high_mi:.0f})"
        )
    elif step == "average":
        why = (
            f"less weather overall than {rival} "
            f"(average risk {w.average_risk:.2f} vs {other.average_risk:.2f})"
        )
    else:  # "time": only reachable when travel times are exactly equal
        why = f"same weather risk as {rival}"
    return f"{name}: {why}; {slower}.{note}"


def _duration(seconds: float) -> str:
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    return f"{hours} h" if hours else f"{minutes} min"
