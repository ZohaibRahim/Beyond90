"""Rolling observable pressing metrics, built incrementally from released public events.

All metrics are keyed by the team being assessed as the potential PRESSING team
(``team``); "opp" metrics describe that team's opponent's build-up. Time is
"elapsed match time": period 1 clock, then the observed period-1 length plus the
period 2 clock.

Definitions (team frame = coordinates where that team attacks toward x = 105):
- high pressure: pressure by ``team`` at x >= 70 in its own frame.
- high regain: possession_change won by ``team`` at x >= 70 in its own frame.
- opp build-up pass: pass by the opponent starting at x < 35 in the opponent's frame
  (the opponent's defensive third, where a high press engages it).
- opp defensive-third completion: completed / all opp build-up passes.
- opp long pass: opponent pass of >= 30 m (any start location).
- opp keeper distribution: passes by the opponent's current goalkeeper; long = >= 35 m.
- opp controlled time: time the opponent controlled the ball (see analytics.possession).
  Stored as intervals; a window counts only the overlapping part of each interval. An
  interval is known only once the event that ends it has been released, so the
  possession in progress at the query time is not yet counted.

Events are counted at their START time; a window [a, b) holds released events that
started in it.

These are counts and rates of observable events. They describe associations only;
no metric labels any individual pass or turnover as caused by pressure.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from beyond90.analytics.possession import TimeCategory, categorize_interval
from beyond90.schemas import (
    MatchEvent,
    MatchSetup,
    MatchStateTracker,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    PossessionChangeEvent,
    PressureEvent,
)
from beyond90.schemas.events import PITCH_LENGTH_M

ATTACKING_THIRD_X = 70.0
DEFENSIVE_THIRD_X = 35.0
LONG_PASS_M = 30.0
KEEPER_LONG_M = 35.0

# Minimum denominators below which a rate is reported as None (insufficient data).
MIN_BUILDUP_PASSES = 10
MIN_PASSES = 20
MIN_KEEPER_PASSES = 3
MIN_CONTROLLED_MIN = 2.0

SERIES = (
    "pressures", "high_pressures", "high_regains",
    "opp_passes", "opp_long_passes", "opp_buildup_passes", "opp_buildup_completed",
    "opp_keeper_passes", "opp_keeper_long",
)
# Evidence keys: every counted series plus the opponent's controlled-possession intervals
# (identified by the event that starts each interval).
EVIDENCE_KEYS = SERIES + ("opp_controlled_intervals",)


class _Series:
    """Time-stamped values with prefix sums for O(log n) window queries."""

    def __init__(self) -> None:
        self.times: list[int] = []
        self.cumulative: list[float] = [0.0]
        self.ids: list[str] = []

    def add(self, t: int, value: float = 1.0, event_id: str = "") -> None:
        self.times.append(t)
        self.cumulative.append(self.cumulative[-1] + value)
        self.ids.append(event_id)

    def _span(self, start: int, end: int) -> tuple[int, int]:
        return bisect_left(self.times, start), bisect_left(self.times, end)

    def total(self, start: int, end: int) -> float:
        lo, hi = self._span(start, end)
        return self.cumulative[hi] - self.cumulative[lo]

    def event_ids(self, start: int, end: int) -> list[str]:
        lo, hi = self._span(start, end)
        return self.ids[lo:hi]


class _IntervalSeries:
    """Non-overlapping, time-ordered [start, end) intervals. A window query counts only the
    part of each interval that overlaps the window."""

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.cumulative: list[int] = [0]
        self.ids: list[str] = []

    def add(self, start: int, end: int, event_id: str) -> None:
        assert end >= start and (not self.ends or start >= self.ends[-1]), "intervals must be ordered"
        if end == start:
            return  # zero duration: contributes no time and is not evidence
        self.starts.append(start)
        self.ends.append(end)
        self.cumulative.append(self.cumulative[-1] + end - start)
        self.ids.append(event_id)

    def _span(self, start: int, end: int) -> tuple[int, int]:
        # Intervals with end > start and start < end overlap the window.
        return bisect_right(self.ends, start), bisect_left(self.starts, end)

    def total(self, start: int, end: int) -> int:
        lo, hi = self._span(start, end)
        if end <= start or lo >= hi:
            return 0
        overlap = self.cumulative[hi] - self.cumulative[lo]
        overlap -= max(0, start - self.starts[lo])
        overlap -= max(0, self.ends[hi - 1] - end)
        return overlap

    def event_ids(self, start: int, end: int) -> list[str]:
        lo, hi = self._span(start, end)
        return self.ids[lo:hi]


@dataclass(frozen=True)
class WindowMetrics:
    team_id: str
    start_ms: int
    end_ms: int
    pressures: int
    high_pressures: int
    high_regains: int
    opp_buildup_passes: int
    opp_buildup_completed: int
    opp_passes: int
    opp_long_passes: int
    opp_keeper_passes: int
    opp_keeper_long: int
    opp_controlled_min: float

    @staticmethod
    def _rate(n: float, d: float, minimum: float) -> float | None:
        return n / d if d >= minimum and d > 0 else None

    @property
    def high_pressures_per_buildup_pass(self) -> float | None:
        return self._rate(self.high_pressures, self.opp_buildup_passes, MIN_BUILDUP_PASSES)

    @property
    def high_regains_per_buildup_pass(self) -> float | None:
        return self._rate(self.high_regains, self.opp_buildup_passes, MIN_BUILDUP_PASSES)

    @property
    def high_pressures_per_opp_controlled_min(self) -> float | None:
        return self._rate(self.high_pressures, self.opp_controlled_min, MIN_CONTROLLED_MIN)

    @property
    def opp_defensive_third_completion(self) -> float | None:
        return self._rate(self.opp_buildup_completed, self.opp_buildup_passes, MIN_BUILDUP_PASSES)

    @property
    def opp_long_pass_share(self) -> float | None:
        return self._rate(self.opp_long_passes, self.opp_passes, MIN_PASSES)

    @property
    def opp_keeper_long_share(self) -> float | None:
        return self._rate(self.opp_keeper_long, self.opp_keeper_passes, MIN_KEEPER_PASSES)

    def as_dict(self) -> dict[str, float | int | None]:
        def r(v: float | None) -> float | None:
            return None if v is None else round(v, 4)

        return {
            "window_start_ms": self.start_ms, "window_end_ms": self.end_ms,
            "pressures": self.pressures, "high_pressures": self.high_pressures,
            "high_regains": self.high_regains, "opp_buildup_passes": self.opp_buildup_passes,
            "opp_buildup_completed": self.opp_buildup_completed, "opp_passes": self.opp_passes,
            "opp_long_passes": self.opp_long_passes, "opp_keeper_passes": self.opp_keeper_passes,
            "opp_keeper_long": self.opp_keeper_long, "opp_controlled_min": round(self.opp_controlled_min, 3),
            "high_pressures_per_buildup_pass": r(self.high_pressures_per_buildup_pass),
            "high_regains_per_buildup_pass": r(self.high_regains_per_buildup_pass),
            "high_pressures_per_opp_controlled_min": r(self.high_pressures_per_opp_controlled_min),
            "opp_defensive_third_completion": r(self.opp_defensive_third_completion),
            "opp_long_pass_share": r(self.opp_long_pass_share),
            "opp_keeper_long_share": r(self.opp_keeper_long_share),
        }


class RollingState:
    """Ingests released events in order; answers window queries. No look-ahead."""

    def __init__(self, setup: MatchSetup) -> None:
        self.setup = setup
        self.tracker = MatchStateTracker(setup)
        self.period1_end_ms: int | None = None
        self.ingested = 0
        self._series = {(t, k): _Series() for t in setup.team_ids for k in SERIES}
        self._controlled = {t: _IntervalSeries() for t in setup.team_ids}  # keyed by presser
        self._prev: MatchEvent | None = None
        self._prev_ball = None
        self._prev_possession: str | None = None

    def elapsed_ms(self, period: int, clock_ms: int) -> int | None:
        if period == 1:
            return clock_ms
        return None if self.period1_end_ms is None else self.period1_end_ms + clock_ms

    def _frame_x(self, team: str, period: int, x: float) -> float:
        return x if self.setup.attacks_toward_x105(team, period) else PITCH_LENGTH_M - x

    def ingest(self, e: MatchEvent) -> None:
        setup = self.setup
        t = self.elapsed_ms(e.period, e.clock_ms)
        assert t is not None, "period 2 event before period 1 ended"
        prev = self._prev
        if prev is not None and prev.period == e.period:
            if categorize_interval(self._prev_ball, e) is TimeCategory.CONTROLLED:
                holder = self._prev_possession
                presser = setup.opponent_id(holder)
                start = self.elapsed_ms(prev.period, prev.clock_ms)
                self._controlled[presser].add(start, start + e.clock_ms - prev.clock_ms, prev.event_id)

        keeper_before = dict(self.tracker.goalkeeper)
        self.tracker.apply(e)

        if isinstance(e, PressureEvent):
            self._series[(e.team_id, "pressures")].add(t, 1, e.event_id)
            if self._frame_x(e.team_id, e.period, e.location.x) >= ATTACKING_THIRD_X:
                self._series[(e.team_id, "high_pressures")].add(t, 1, e.event_id)
        elif isinstance(e, PossessionChangeEvent):
            if self._frame_x(e.team_id, e.period, e.location.x) >= ATTACKING_THIRD_X:
                self._series[(e.team_id, "high_regains")].add(t, 1, e.event_id)
        elif isinstance(e, PassEvent):
            presser = setup.opponent_id(e.team_id)
            s = lambda key: self._series[(presser, key)]  # noqa: E731
            length = math.hypot(e.end_location.x - e.location.x, e.end_location.y - e.location.y)
            eid = e.event_id
            s("opp_passes").add(t, 1, eid)
            if length >= LONG_PASS_M:
                s("opp_long_passes").add(t, 1, eid)
            if self._frame_x(e.team_id, e.period, e.location.x) < DEFENSIVE_THIRD_X:
                s("opp_buildup_passes").add(t, 1, eid)
                if e.outcome is PassOutcome.COMPLETE:
                    s("opp_buildup_completed").add(t, 1, eid)
            if e.player_id == keeper_before[e.team_id]:
                s("opp_keeper_passes").add(t, 1, eid)
                if length >= KEEPER_LONG_M:
                    s("opp_keeper_long").add(t, 1, eid)
        elif isinstance(e, PeriodEndEvent) and e.period == 1:
            self.period1_end_ms = e.clock_ms

        self._prev, self._prev_ball, self._prev_possession = e, self.tracker.ball, self.tracker.possession
        self.ingested += 1

    def window(self, team: str, start_ms: int, end_ms: int) -> WindowMetrics:
        start_ms = max(0, start_ms)
        g = lambda key: self._series[(team, key)].total(start_ms, end_ms)  # noqa: E731
        return WindowMetrics(
            team_id=team, start_ms=start_ms, end_ms=end_ms,
            pressures=int(g("pressures")), high_pressures=int(g("high_pressures")),
            high_regains=int(g("high_regains")), opp_buildup_passes=int(g("opp_buildup_passes")),
            opp_buildup_completed=int(g("opp_buildup_completed")), opp_passes=int(g("opp_passes")),
            opp_long_passes=int(g("opp_long_passes")), opp_keeper_passes=int(g("opp_keeper_passes")),
            opp_keeper_long=int(g("opp_keeper_long")),
            opp_controlled_min=self._controlled[team].total(start_ms, end_ms) / 60_000,
        )

    def event_ids(self, team: str, key: str, start_ms: int, end_ms: int) -> list[str]:
        """Ids of the events counted under ``key`` in [start_ms, end_ms) (see EVIDENCE_KEYS)."""
        if key == "opp_controlled_intervals":
            return self._controlled[team].event_ids(max(0, start_ms), end_ms)
        return self._series[(team, key)].event_ids(max(0, start_ms), end_ms)

    def evidence(self, team: str, start_ms: int, end_ms: int) -> dict[str, list[str]]:
        """Every numerator and denominator event behind ``window(team, start_ms, end_ms)``."""
        return {k: self.event_ids(team, k, start_ms, end_ms) for k in EVIDENCE_KEYS}
