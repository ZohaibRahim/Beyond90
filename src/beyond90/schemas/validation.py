"""Football-rule validation of a public event stream.

``MatchStateTracker`` consumes events one at a time (so it is usable live, with
no look-ahead) and raises ``MatchValidationError`` on the first violation of:
chronology, player eligibility, substitutions, possession continuity, restart
rules and pitch orientation.

Ball states:
- DEAD: only ``restart``, ``substitution`` or ``period_end`` may follow.
- IN_PLAY: ``possession`` holds the ball; opponents may pressure/tackle/intercept/foul.
- TURNOVER_PENDING: a tackle, interception or incomplete pass must be resolved
  by a ``possession_change`` with the matching cause.
- LOOSE: after a saved/blocked/woodwork shot; resolved by a rebound action of the
  attacking team, a ``possession_change`` (cause ``shot``), or a restart if the
  ball went out (corner to attackers, goal kick to defenders, or throw-in). A
  substitution while LOOSE implies the ball went out, so a restart must follow.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from beyond90.schemas.events import (
    CENTRE_SPOT,
    PITCH_LENGTH_M,
    PITCH_WIDTH_M,
    FoulEvent,
    InterceptionEvent,
    MatchEvent,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    PitchLocation,
    PossessionChangeCause,
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
from beyond90.schemas.match_setup import MatchSetup, Position

MIN_PERIOD_MS = 45 * 60_000
GOAL_AREA_DEPTH_M = 5.5
GOAL_AREA_HALF_WIDTH_M = 9.16


class MatchValidationError(ValueError):
    pass


class BallState(StrEnum):
    DEAD = "dead"
    IN_PLAY = "in_play"
    TURNOVER_PENDING = "turnover_pending"
    LOOSE = "loose"


_OUT_OF_PLAY_RESTARTS = frozenset({RestartType.THROW_IN, RestartType.GOAL_KICK, RestartType.CORNER_KICK})


class MatchStateTracker:
    def __init__(self, setup: MatchSetup) -> None:
        self.setup = setup
        self.on_pitch: dict[str, set[str]] = {t.team_id: set(t.starting_xi) for t in setup.teams}
        self.unused_bench: dict[str, set[str]] = {t.team_id: set(t.bench) for t in setup.teams}
        self.goalkeeper: dict[str, str] = {t.team_id: t.starting_goalkeeper_id for t in setup.teams}
        self.substitutions: dict[str, int] = {tid: 0 for tid in setup.team_ids}
        self.score: dict[str, int] = {tid: 0 for tid in setup.team_ids}
        self.period = 1
        self.period_over = False
        self.match_over = False
        self.ball = BallState.DEAD
        self.possession: str | None = None
        self._pending_cause: PossessionChangeCause | None = None
        self._loose_stopped = False
        self._expected_team: str | None = setup.kickoff_team_id(1)
        self._expected_types: frozenset[RestartType] = frozenset({RestartType.KICKOFF})
        self._seen_ids: set[str] = set()
        self._prev: MatchEvent | None = None

    # -- public API ---------------------------------------------------------

    def apply(self, event: MatchEvent) -> None:
        self._check_stream(event)
        getattr(self, f"_on_{event.event_type}")(event)
        if self.ball is not BallState.LOOSE:
            self._loose_stopped = False
        self._seen_ids.add(event.event_id)
        self._prev = event

    def finish(self) -> None:
        if not self.match_over:
            raise MatchValidationError("match is incomplete: period 2 has not ended")

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _fail(event: MatchEvent, message: str) -> None:
        raise MatchValidationError(f"{event.event_id}: {message}")

    def _require_ball(self, event: MatchEvent, *states: BallState) -> None:
        if self.ball not in states:
            self._fail(event, f"{event.event_type} not allowed while ball is {self.ball}")
        if self._loose_stopped and event.event_type not in ("restart", "substitution", "period_end"):
            self._fail(event, "play was stopped for a substitution; a restart must follow")

    def _require_on_pitch(self, event: MatchEvent, team_id: str, player_id: str) -> None:
        if team_id not in self.on_pitch:
            self._fail(event, f"unknown team {team_id!r}")
        if player_id not in self.on_pitch[team_id]:
            self._fail(event, f"player {player_id!r} is not on the pitch for {team_id}")

    def _require_possessor(self, event: MatchEvent, team_id: str) -> None:
        if team_id != self.possession:
            self._fail(event, f"{team_id} acted on the ball but {self.possession} has possession")

    def _require_defender(self, event: MatchEvent, team_id: str) -> None:
        if self.possession is None or team_id == self.possession:
            self._fail(event, f"{team_id} made a defensive action while in possession")

    def _attacking(self, location: PitchLocation, team_id: str) -> PitchLocation:
        return self.setup.to_attacking_frame(location, team_id, self.period)

    def _set_dead(self, restart_team: str | None, types: Iterable[RestartType]) -> None:
        self.ball = BallState.DEAD
        self._expected_team = restart_team
        self._expected_types = frozenset(types)
        self._pending_cause = None

    def _check_stream(self, event: MatchEvent) -> None:
        if self.match_over:
            self._fail(event, "event after the end of the match")
        if event.match_id != self.setup.match_id:
            self._fail(event, "match_id does not match the setup")
        if event.event_id in self._seen_ids:
            self._fail(event, "duplicate event_id")
        if event.related_event_id is not None and event.related_event_id not in self._seen_ids:
            self._fail(event, "related_event_id is not an earlier event")
        prev = self._prev
        if prev is not None:
            if event.sequence <= prev.sequence:
                self._fail(event, "sequence not strictly increasing")
            if (event.period, event.clock_ms) < (prev.period, prev.clock_ms):
                self._fail(event, "match time went backwards")
        if event.period != self.period:
            if not (self.period_over and event.period == self.period + 1):
                self._fail(event, f"period {event.period} event before period {self.period} ended")
            self.period = event.period
            self.period_over = False
            self.possession = None
            self._set_dead(self.setup.kickoff_team_id(self.period), {RestartType.KICKOFF})
        elif self.period_over:
            self._fail(event, "event after the end of the period")

    # -- handlers -----------------------------------------------------------

    def _on_restart(self, e: RestartEvent) -> None:
        self._require_ball(e, BallState.DEAD, BallState.LOOSE)
        if self.ball is BallState.LOOSE:
            if e.restart_type not in _OUT_OF_PLAY_RESTARTS:
                self._fail(e, f"{e.restart_type} cannot follow a loose ball")
            if e.restart_type is RestartType.CORNER_KICK and e.team_id != self.possession:
                self._fail(e, "corner after a shot must go to the attacking team")
            if e.restart_type is RestartType.GOAL_KICK and e.team_id == self.possession:
                self._fail(e, "goal kick after a shot must go to the defending team")
        else:
            if self._expected_team is not None and e.team_id != self._expected_team:
                self._fail(e, f"restart should be taken by {self._expected_team}")
            if e.restart_type not in self._expected_types:
                self._fail(e, f"{e.restart_type} not allowed here; expected {sorted(self._expected_types)}")
        self._require_on_pitch(e, e.team_id, e.player_id)
        self._check_restart_location(e)
        self.ball = BallState.IN_PLAY
        self.possession = e.team_id
        self._expected_team = None
        self._expected_types = frozenset()

    def _check_restart_location(self, e: RestartEvent) -> None:
        loc, att = e.location, self._attacking(e.location, e.team_id)
        t = e.restart_type
        if t is RestartType.KICKOFF and (loc.x, loc.y) != CENTRE_SPOT:
            self._fail(e, "kickoff must be taken from the centre spot")
        if t is RestartType.THROW_IN and loc.y not in (0.0, PITCH_WIDTH_M):
            self._fail(e, "throw-in must be taken on a touchline")
        if t is RestartType.CORNER_KICK and not (att.x == PITCH_LENGTH_M and loc.y in (0.0, PITCH_WIDTH_M)):
            self._fail(e, "corner must be taken at a corner of the attacked goal line")
        if t is RestartType.GOAL_KICK and not (
            att.x <= GOAL_AREA_DEPTH_M and abs(att.y - PITCH_WIDTH_M / 2) <= GOAL_AREA_HALF_WIDTH_M
        ):
            self._fail(e, "goal kick must be taken from the team's own goal area")

    def _on_pass(self, e: PassEvent) -> None:
        self._require_ball(e, BallState.IN_PLAY, BallState.LOOSE)
        self._require_possessor(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        self.ball = BallState.IN_PLAY
        opponent = self.setup.opponent_id(e.team_id)
        if e.outcome is PassOutcome.COMPLETE:
            assert e.recipient_id is not None
            self._require_on_pitch(e, e.team_id, e.recipient_id)
        elif e.outcome is PassOutcome.INCOMPLETE:
            self.ball = BallState.TURNOVER_PENDING
            self._pending_cause = PossessionChangeCause.INCOMPLETE_PASS
        elif e.outcome is PassOutcome.OFFSIDE:
            self._set_dead(opponent, {RestartType.FREE_KICK})
        else:
            self._set_dead(opponent, self._out_of_play_restarts(e, opponent))

    def _out_of_play_restarts(self, e: PassEvent, restart_team: str) -> set[RestartType]:
        end = e.end_location
        types: set[RestartType] = set()
        if end.y in (0.0, PITCH_WIDTH_M):
            types.add(RestartType.THROW_IN)
        if end.x in (0.0, PITCH_LENGTH_M):
            att = self._attacking(end, restart_team)
            types.add(RestartType.CORNER_KICK if att.x == PITCH_LENGTH_M else RestartType.GOAL_KICK)
        if not types:
            self._fail(e, "out-of-play pass must end on a boundary line")
        return types

    def _on_shot(self, e: ShotEvent) -> None:
        self._require_ball(e, BallState.IN_PLAY, BallState.LOOSE)
        self._require_possessor(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        if self._attacking(e.location, e.team_id).x <= PITCH_LENGTH_M / 2:
            self._fail(e, "shot taken from the team's own half (check pitch orientation)")
        opponent = self.setup.opponent_id(e.team_id)
        if e.outcome is ShotOutcome.GOAL:
            self.score[e.team_id] += 1
            self.possession = None
            self._set_dead(opponent, {RestartType.KICKOFF})
        elif e.outcome is ShotOutcome.OFF_TARGET:
            self._set_dead(opponent, {RestartType.GOAL_KICK})
        else:
            self.ball = BallState.LOOSE
            self._pending_cause = PossessionChangeCause.SHOT

    def _on_tackle(self, e: TackleEvent) -> None:
        self._require_ball(e, BallState.IN_PLAY)
        self._require_defender(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        self._require_on_pitch(e, self.possession or "", e.opponent_player_id)
        if e.outcome is TackleOutcome.WON:
            self.ball = BallState.TURNOVER_PENDING
            self._pending_cause = PossessionChangeCause.TACKLE

    def _on_pressure(self, e: PressureEvent) -> None:
        self._require_ball(e, BallState.IN_PLAY)
        self._require_defender(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        self._require_on_pitch(e, self.possession or "", e.opponent_player_id)

    def _on_interception(self, e: InterceptionEvent) -> None:
        after_bad_pass = (
            self.ball is BallState.TURNOVER_PENDING
            and self._pending_cause is PossessionChangeCause.INCOMPLETE_PASS
        )
        if not (self.ball is BallState.IN_PLAY or after_bad_pass):
            self._fail(e, f"interception not allowed while ball is {self.ball}")
        self._require_defender(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        self.ball = BallState.TURNOVER_PENDING
        self._pending_cause = PossessionChangeCause.INTERCEPTION

    def _on_possession_change(self, e: PossessionChangeEvent) -> None:
        self._require_ball(e, BallState.TURNOVER_PENDING, BallState.LOOSE)
        if e.cause is not self._pending_cause:
            self._fail(e, f"possession change cause {e.cause} does not match {self._pending_cause}")
        if e.previous_team_id != self.possession:
            self._fail(e, f"previous_team_id {e.previous_team_id} did not have possession")
        self._require_defender(e, e.team_id)
        if e.player_id is not None:
            self._require_on_pitch(e, e.team_id, e.player_id)
        self.ball = BallState.IN_PLAY
        self.possession = e.team_id
        self._pending_cause = None

    def _on_foul(self, e: FoulEvent) -> None:
        self._require_ball(e, BallState.IN_PLAY)
        self._require_defender(e, e.team_id)
        self._require_on_pitch(e, e.team_id, e.player_id)
        self._require_on_pitch(e, self.possession or "", e.opponent_player_id)
        self._set_dead(self.setup.opponent_id(e.team_id), {RestartType.FREE_KICK})

    def _on_substitution(self, e: SubstitutionEvent) -> None:
        self._require_ball(e, BallState.DEAD, BallState.LOOSE)
        self._loose_stopped = self.ball is BallState.LOOSE
        self._require_on_pitch(e, e.team_id, e.player_off_id)
        if e.player_on_id not in self.unused_bench[e.team_id]:
            self._fail(e, f"{e.player_on_id} is not an unused substitute for {e.team_id}")
        if self.substitutions[e.team_id] >= self.setup.max_substitutions:
            self._fail(e, f"{e.team_id} exceeded {self.setup.max_substitutions} substitutions")
        team = self.setup.team(e.team_id)
        if e.player_off_id == self.goalkeeper[e.team_id]:
            if team.player(e.player_on_id).position is not Position.GOALKEEPER:
                self._fail(e, "a goalkeeper must be replaced by a goalkeeper")
            self.goalkeeper[e.team_id] = e.player_on_id
        self.on_pitch[e.team_id].remove(e.player_off_id)
        self.on_pitch[e.team_id].add(e.player_on_id)
        self.unused_bench[e.team_id].remove(e.player_on_id)
        self.substitutions[e.team_id] += 1

    def _on_period_end(self, e: PeriodEndEvent) -> None:
        self._require_ball(e, BallState.DEAD, BallState.IN_PLAY, BallState.LOOSE)
        if e.clock_ms < MIN_PERIOD_MS:
            self._fail(e, "a period lasts at least 45 minutes")
        self.period_over = True
        self.possession = None
        self._set_dead(None, ())
        if self.period == 2:
            self.match_over = True


def validate_match(setup: MatchSetup, events: Iterable[MatchEvent]) -> MatchStateTracker:
    """Validate a complete match; returns the final tracker (e.g. for the score)."""
    tracker = MatchStateTracker(setup)
    for event in events:
        tracker.apply(event)
    tracker.finish()
    return tracker
