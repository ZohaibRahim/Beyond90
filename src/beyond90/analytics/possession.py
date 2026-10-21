"""Time-based possession estimate and possession sequences from public events.

Both replay the stream through ``MatchStateTracker`` (no look-ahead), so they use
only observable match state.

Time accounting: every interval between consecutive events in the same period
falls into exactly ONE category, so the categories sum to elapsed match time:

- CONTROLLED: ball in play and held by a team (credited to that team).
- CONTESTED: ball in play but nobody in control: an incomplete pass in flight,
  a won tackle or interception before the turnover is recorded, or a loose ball
  after a parried/blocked shot that is then recovered.
- STOPPAGE: ball out of play (after fouls, offsides, goals, balls out, and
  substitutions). A loose ball followed by a restart or substitution proves the
  ball went out; the exact moment is not observed, so that whole interval is a
  stoppage.

Possession share = a team's CONTROLLED time / all CONTROLLED time. Limitations:
event timestamps are the only clock, so a completed pass in flight is credited
to the passer, and play between events belongs to whoever held the ball at the
earlier event. An interval's category is final once the next event arrives.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from beyond90.schemas import (
    MatchEvent,
    MatchSetup,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    PossessionChangeEvent,
    RestartEvent,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
)
from beyond90.schemas.validation import BallState, MatchStateTracker


class TimeCategory(StrEnum):
    CONTROLLED = "controlled"
    CONTESTED = "contested"
    STOPPAGE = "stoppage"


@dataclass(frozen=True)
class PossessionInterval:
    start_event: MatchEvent
    duration_ms: int
    category: TimeCategory
    team_id: str | None  # team in control; set only for CONTROLLED


@dataclass
class PossessionSummary:
    controlled_ms: dict[str, int]
    contested_ms: int = 0
    stoppage_ms: int = 0

    @property
    def ball_in_play_ms(self) -> int:
        """Controlled + contested."""
        return sum(self.controlled_ms.values()) + self.contested_ms

    @property
    def elapsed_ms(self) -> int:
        return self.ball_in_play_ms + self.stoppage_ms

    def share(self, team_id: str) -> float | None:
        held = sum(self.controlled_ms.values())
        return self.controlled_ms[team_id] / held if held else None


def _categorize(team: str | None, ball: BallState, next_event: MatchEvent) -> TimeCategory:
    if ball is BallState.IN_PLAY:
        return TimeCategory.CONTROLLED
    if ball is BallState.DEAD:
        return TimeCategory.STOPPAGE
    if ball is BallState.LOOSE and isinstance(next_event, (RestartEvent, SubstitutionEvent)):
        return TimeCategory.STOPPAGE
    return TimeCategory.CONTESTED


def possession_intervals(setup: MatchSetup, events: Iterable[MatchEvent]) -> list[PossessionInterval]:
    tracker = MatchStateTracker(setup)
    intervals: list[PossessionInterval] = []
    prev: MatchEvent | None = None
    prev_state: tuple[str | None, BallState] | None = None
    for e in events:
        if prev is not None and prev_state is not None and prev.period == e.period:
            team, ball = prev_state
            category = _categorize(team, ball, e)
            intervals.append(PossessionInterval(prev, e.clock_ms - prev.clock_ms, category,
                                                team if category is TimeCategory.CONTROLLED else None))
        tracker.apply(e)
        prev, prev_state = e, (tracker.possession, tracker.ball)
    return intervals


def summarize_possession(
    setup: MatchSetup,
    intervals: Iterable[PossessionInterval],
    include: Callable[[MatchEvent], bool] | None = None,
) -> PossessionSummary:
    summary = PossessionSummary(controlled_ms={tid: 0 for tid in setup.team_ids})
    for iv in intervals:
        if include is not None and not include(iv.start_event):
            continue
        if iv.category is TimeCategory.CONTROLLED:
            assert iv.team_id is not None
            summary.controlled_ms[iv.team_id] += iv.duration_ms
        elif iv.category is TimeCategory.STOPPAGE:
            summary.stoppage_ms += iv.duration_ms
        else:
            summary.contested_ms += iv.duration_ms
    return summary


@dataclass
class PossessionSequence:
    """An unbroken spell of one team's possession (restarts by the same team continue it)."""

    team_id: str
    events: list[MatchEvent] = field(default_factory=list)
    end_reason: str = ""

    @property
    def passes(self) -> int:
        return sum(isinstance(e, PassEvent) and e.team_id == self.team_id for e in self.events)

    @property
    def duration_ms(self) -> int:
        return self.events[-1].clock_ms - self.events[0].clock_ms


def _end_reason(last_own: MatchEvent | None, next_event: MatchEvent | None) -> str:
    if isinstance(last_own, ShotEvent):
        return "goal" if last_own.outcome is ShotOutcome.GOAL else f"shot ({last_own.outcome})"
    if isinstance(next_event, PossessionChangeEvent):
        return f"turnover ({next_event.cause})"
    if isinstance(last_own, PassEvent) and last_own.outcome in (PassOutcome.OUT_OF_PLAY, PassOutcome.OFFSIDE):
        return f"pass {last_own.outcome}"
    if isinstance(next_event, PeriodEndEvent) or next_event is None:
        return "period end"
    return "other"


def possession_sequences(setup: MatchSetup, events: Iterable[MatchEvent]) -> list[PossessionSequence]:
    tracker = MatchStateTracker(setup)
    sequences: list[PossessionSequence] = []
    current: PossessionSequence | None = None

    def close(next_event: MatchEvent | None) -> None:
        nonlocal current
        if current is not None and current.events:
            own = [e for e in current.events if getattr(e, "team_id", None) == current.team_id]
            current.end_reason = _end_reason(own[-1] if own else None, next_event)
            sequences.append(current)
        current = None

    for e in events:
        before = tracker.possession
        tracker.apply(e)
        after = tracker.possession
        if isinstance(e, (PeriodEndEvent, SubstitutionEvent)):
            if isinstance(e, PeriodEndEvent):
                close(e)
            continue
        if after is not None and (current is None or after != current.team_id):
            close(e)
            current = PossessionSequence(after)
        if current is not None:
            current.events.append(e)
        if after is None and before is not None:  # goal: possession ends with the shot
            close(None)
    close(None)
    return sequences
