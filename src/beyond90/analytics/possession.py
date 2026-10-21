"""Time-based possession estimate and possession sequences from public events.

Both replay the stream through ``MatchStateTracker`` (no look-ahead), so they use
only observable match state.

Possession estimate: the time between consecutive events in the same period is
credited to the team in possession while the ball is IN_PLAY. Intervals while
the ball is dead are excluded, and intervals while the ball is contested
(after a tackle/interception/incomplete pass/parried shot, before the turnover is
resolved) are counted as ``contested``. Limitations: event timestamps are the
only clock, so a pass in flight is credited to the passer, and play between
events is assumed to belong to whoever held the ball at the earlier event.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from beyond90.schemas import (
    MatchEvent,
    MatchSetup,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    PossessionChangeEvent,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
)
from beyond90.schemas.validation import BallState, MatchStateTracker


@dataclass(frozen=True)
class PossessionInterval:
    start_event: MatchEvent
    duration_ms: int
    team_id: str | None  # team in possession; None when dead or contested
    ball: BallState


@dataclass
class PossessionSummary:
    in_play_ms: dict[str, int]
    contested_ms: int = 0
    dead_ms: int = 0

    @property
    def ball_in_play_ms(self) -> int:
        return sum(self.in_play_ms.values()) + self.contested_ms

    def share(self, team_id: str) -> float | None:
        held = sum(self.in_play_ms.values())
        return self.in_play_ms[team_id] / held if held else None


def possession_intervals(setup: MatchSetup, events: Iterable[MatchEvent]) -> list[PossessionInterval]:
    tracker = MatchStateTracker(setup)
    intervals: list[PossessionInterval] = []
    prev: MatchEvent | None = None
    prev_state: tuple[str | None, BallState] | None = None
    for e in events:
        if prev is not None and prev_state is not None and prev.period == e.period:
            team, ball = prev_state
            intervals.append(PossessionInterval(prev, e.clock_ms - prev.clock_ms,
                                                team if ball is BallState.IN_PLAY else None, ball))
        tracker.apply(e)
        prev, prev_state = e, (tracker.possession, tracker.ball)
    return intervals


def summarize_possession(
    setup: MatchSetup,
    intervals: Iterable[PossessionInterval],
    include: Callable[[MatchEvent], bool] | None = None,
) -> PossessionSummary:
    summary = PossessionSummary(in_play_ms={tid: 0 for tid in setup.team_ids})
    for iv in intervals:
        if include is not None and not include(iv.start_event):
            continue
        if iv.team_id is not None:
            summary.in_play_ms[iv.team_id] += iv.duration_ms
        elif iv.ball is BallState.DEAD:
            summary.dead_ms += iv.duration_ms
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
