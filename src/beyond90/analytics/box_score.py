"""Deterministic team statistics computed from public events only."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields

from beyond90.schemas import (
    FoulEvent,
    InterceptionEvent,
    MatchEvent,
    MatchSetup,
    PassEvent,
    PassOutcome,
    PossessionChangeEvent,
    PressureEvent,
    RestartEvent,
    RestartType,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
    TackleEvent,
    TackleOutcome,
)

ATTACKING_THIRD_X = 70.0
WINDOW_LABELS = ("0-15", "15-30", "30-45+", "45-60", "60-75", "75-90+")


@dataclass
class TeamStats:
    team_id: str
    goals: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes: int = 0
    passes_completed: int = 0
    pressures: int = 0
    pressures_attacking_third: int = 0
    tackles: int = 0
    tackles_won: int = 0
    interceptions: int = 0
    turnovers_won: int = 0
    turnovers_won_attacking_third: int = 0
    fouls: int = 0
    offsides: int = 0
    corners: int = 0
    throw_ins: int = 0
    goal_kicks: int = 0
    free_kicks: int = 0
    substitutions: int = 0

    @property
    def pass_completion(self) -> float | None:
        return self.passes_completed / self.passes if self.passes else None

    def as_dict(self) -> dict[str, int]:
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "team_id"}


def window_index(event: MatchEvent) -> int:
    """15-minute window 0..5; stoppage time joins the last window of its half."""
    return (0 if event.period == 1 else 3) + min(event.clock_ms // (15 * 60_000), 2)


def compute_team_stats(
    setup: MatchSetup,
    events: Iterable[MatchEvent],
    include: Callable[[MatchEvent], bool] | None = None,
) -> dict[str, TeamStats]:
    stats = {tid: TeamStats(tid) for tid in setup.team_ids}

    def in_attacking_third(e: MatchEvent, location) -> bool:
        return setup.to_attacking_frame(location, e.team_id, e.period).x >= ATTACKING_THIRD_X

    for e in events:
        if include is not None and not include(e):
            continue
        match e:
            case ShotEvent():
                s = stats[e.team_id]
                s.shots += 1
                s.goals += e.outcome is ShotOutcome.GOAL
                s.shots_on_target += e.outcome in (ShotOutcome.GOAL, ShotOutcome.SAVED)
            case PassEvent():
                s = stats[e.team_id]
                s.passes += 1
                s.passes_completed += e.outcome is PassOutcome.COMPLETE
                s.offsides += e.outcome is PassOutcome.OFFSIDE
            case PressureEvent():
                stats[e.team_id].pressures += 1
                stats[e.team_id].pressures_attacking_third += in_attacking_third(e, e.location)
            case TackleEvent():
                stats[e.team_id].tackles += 1
                stats[e.team_id].tackles_won += e.outcome is TackleOutcome.WON
            case InterceptionEvent():
                stats[e.team_id].interceptions += 1
            case PossessionChangeEvent():
                stats[e.team_id].turnovers_won += 1
                stats[e.team_id].turnovers_won_attacking_third += in_attacking_third(e, e.location)
            case FoulEvent():
                stats[e.team_id].fouls += 1
            case RestartEvent():
                s = stats[e.team_id]
                s.corners += e.restart_type is RestartType.CORNER_KICK
                s.throw_ins += e.restart_type is RestartType.THROW_IN
                s.goal_kicks += e.restart_type is RestartType.GOAL_KICK
                s.free_kicks += e.restart_type is RestartType.FREE_KICK
            case SubstitutionEvent():
                stats[e.team_id].substitutions += 1
    return stats
