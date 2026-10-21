"""Seeded, possession-based match engine.

The engine models one ball carrier at a time. Each step the defending team may
press (probability set by its HIDDEN pressing intensity and the ball's zone),
then the carrier may be fouled or tackled, shoot, or pass. Hidden settings only
change probabilities; events record observable outcomes, never the settings.

Internally the ball position is stored in fixed pitch coordinates; decisions are
made in the acting team's attacking frame (attacking toward x = 105).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from beyond90.ground_truth import (
    AppliedIntervention,
    GroundTruthRecord,
    InterventionManifest,
    PressingChange,
    PressingIntensity,
)
from beyond90.schemas import (
    BodyPart,
    FoulEvent,
    InterceptionEvent,
    MatchEvent,
    MatchSetup,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    PitchLocation,
    Position,
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
    validate_match,
)
from beyond90.schemas.events import CENTRE_SPOT, PITCH_LENGTH_M, PITCH_WIDTH_M
from beyond90.simulator.scenario import match_id_for_seed, pressing_switch_script
from beyond90.simulator.teams import build_match_setup

SIMULATOR_VERSION = "0.1.0"

PERIOD_MS = 45 * 60_000
LOW, MEDIUM, HIGH = PressingIntensity.LOW, PressingIntensity.MEDIUM, PressingIntensity.HIGH
GK, DF, MF, FW = Position.GOALKEEPER, Position.DEFENDER, Position.MIDFIELDER, Position.FORWARD

# Chance the defending team presses the carrier, by the ball's zone in the
# ATTACKING team's frame: (own third, middle third, final third).
PRESS_PROB = {LOW: (0.12, 0.20, 0.36), MEDIUM: (0.20, 0.27, 0.35), HIGH: (0.40, 0.34, 0.33)}
# Pass-completion penalty when pressed; an aggressive press closes space faster.
PRESSED_PASS_PENALTY = {LOW: 0.10, MEDIUM: 0.13, HIGH: 0.17}
FOUL_BASE, FOUL_PRESSED = 0.016, 0.03
TACKLE_BASE, TACKLE_PRESSED = 0.015, 0.06
TACKLE_WIN = 0.6
INTERCEPT_SHARE = 0.15
CROSS_CLEARED_FOR_CORNER = 0.3
SHOT_SCALE = 0.55
GK_RANGE_X = 18.0
# Chance an outfield passer in their own half chooses to play back to the goalkeeper:
# (unpressed, pressed) for defenders and midfielders. Recycling via the keeper is
# a deliberate choice, more common deep and under pressure.
BACK_PASS_PROB = {DF: (0.05, 0.20), MF: (0.015, 0.06)}
BACK_PASS_MAX_X = 45.0
# Keeper distribution: chance of going long (unpressed, pressed).
KEEPER_LONG_PROB = (0.35, 0.75)

# Who is involved, by zone of the ball in that player's own attacking frame.
ZONE_WEIGHTS = (
    {GK: 0.10, DF: 0.50, MF: 0.32, FW: 0.08},
    {GK: 0.01, DF: 0.25, MF: 0.50, FW: 0.24},
    {GK: 0.00, DF: 0.08, MF: 0.40, FW: 0.52},
)
RESTART_DELAY_S = {
    RestartType.KICKOFF: (0, 0),
    RestartType.THROW_IN: (8, 18),
    RestartType.GOAL_KICK: (15, 30),
    RestartType.CORNER_KICK: (20, 35),
    RestartType.FREE_KICK: (15, 35),
}
# Internal (never emitted) contexts for the next carrier action, besides restart types.
CROSS, REBOUND, KEEPER = "cross", "rebound", "keeper"


@dataclass(frozen=True)
class SimulationResult:
    setup: MatchSetup
    events: tuple[MatchEvent, ...]
    ground_truth: GroundTruthRecord


def _zone(x: float) -> int:
    return 0 if x < 35 else 1 if x < 70 else 2


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(max(v, lo), hi)


class _Engine:
    def __init__(self, setup: MatchSetup, script: InterventionManifest) -> None:
        if {b.team_id for b in script.baselines} != set(setup.team_ids):
            raise ValueError("script must give a baseline for both teams")
        for iv in script.interventions:
            if not isinstance(iv, PressingChange):
                raise NotImplementedError(f"simulator does not support {iv.intervention_type} yet")
            if iv.team_id not in setup.team_ids:
                raise ValueError(f"intervention for unknown team {iv.team_id}")
        self.setup = setup
        self.script = script
        self.rng = random.Random(script.simulation_seed)
        self.events: list[MatchEvent] = []
        self.period = 1
        self.clock = 0
        self.pos = {p.player_id: p.position for t in setup.teams for p in t.squad}
        self.on_pitch = {t.team_id: list(t.starting_xi) for t in setup.teams}
        self.bench = {t.team_id: list(t.bench) for t in setup.teams}
        self.came_on: set[str] = set()
        self.goalkeeper = {t.team_id: t.starting_goalkeeper_id for t in setup.teams}
        self.score = {tid: 0 for tid in setup.team_ids}
        self.subs_made = {tid: 0 for tid in setup.team_ids}
        self.sub_plan = {tid: self._plan_subs() for tid in setup.team_ids}
        self.baseline = {b.team_id: b.pressing for b in script.baselines}
        self.applied: dict[str, AppliedIntervention] = {}
        # Ball state.
        self.team: str = setup.kickoff_team_id(1)
        self.carrier: str = ""
        self.ball: tuple[float, float] = CENTRE_SPOT
        self.context: str | None = None
        self.next_restart: tuple[RestartType, str, tuple[float, float]] | None = None

    # -- infrastructure -----------------------------------------------------

    def _plan_subs(self) -> list[int]:
        n = self.rng.choice((3, 4, 4, 5, 5))
        return sorted(0 if self.rng.random() < 0.12 else self.rng.randint(10, 42) * 60_000 for _ in range(n))

    def _att(self, team: str, x: float, y: float) -> tuple[float, float]:
        """Fixed <-> team attacking frame (a 180-degree rotation, its own inverse)."""
        if self.setup.attacks_toward_x105(team, self.period):
            return x, y
        return PITCH_LENGTH_M - x, PITCH_WIDTH_M - y

    def _loc(self, team: str, x: float, y: float) -> PitchLocation:
        """Team-frame point -> fixed-coordinate PitchLocation."""
        fx, fy = self._att(team, _clamp(x, 0, PITCH_LENGTH_M), _clamp(y, 0, PITCH_WIDTH_M))
        return PitchLocation(x=round(fx, 1), y=round(fy, 1))

    def _emit(self, model, **fields) -> MatchEvent:
        seq = len(self.events)
        event = model(event_id=f"{self.setup.match_id}-{seq:05d}", match_id=self.setup.match_id,
                      sequence=seq, period=self.period, clock_ms=self.clock, **fields)
        for iv in self.script.interventions:
            due = (iv.effective_period, iv.effective_clock_ms) <= (self.period, self.clock)
            if due and iv.intervention_id not in self.applied:
                self.applied[iv.intervention_id] = AppliedIntervention(
                    intervention_id=iv.intervention_id, first_event_sequence=seq, first_event_id=event.event_id)
        self.events.append(event)
        return event

    def _pressing(self, team: str) -> PressingIntensity:
        level = self.baseline[team]
        for iv in self.script.interventions:
            if iv.team_id == team and (iv.effective_period, iv.effective_clock_ms) <= (self.period, self.clock):
                level = iv.intensity
        return level

    def _pick(self, team: str, x_team: float, exclude: tuple[str, ...] = (), outfield: bool = False) -> str:
        weights_by_pos = ZONE_WEIGHTS[_zone(x_team)]
        players = [p for p in self.on_pitch[team] if p not in exclude and not (outfield and self.pos[p] is GK)]
        # Goalkeepers only get involved close to their own goal.
        weights = [0.0 if self.pos[p] is GK and x_team > GK_RANGE_X else weights_by_pos[self.pos[p]]
                   for p in players]
        if not any(weights):
            weights = [1.0] * len(players)
        return self.rng.choices(players, weights=weights)[0]

    def _goal_kick_spot(self, team: str) -> tuple[float, float]:
        loc = self._loc(team, 5.5, 34 + self.rng.uniform(-8, 8))
        return (loc.x, loc.y)

    def _restart(self, rtype: RestartType, team: str, spot: tuple[float, float]) -> None:
        self.next_restart = (rtype, team, spot)

    # -- match flow ---------------------------------------------------------

    def run(self) -> None:
        for period in (1, 2):
            self.period, self.clock = period, 0
            end_ms = PERIOD_MS + self.rng.randint(60, 180 if period == 1 else 330) * 1000
            self._restart(RestartType.KICKOFF, self.setup.kickoff_team_id(period), CENTRE_SPOT)
            while True:
                if self.next_restart is not None:
                    if self.clock >= end_ms:
                        break
                    self._substitutions()
                    self._take_restart()
                elif self.clock >= end_ms:
                    break
                else:
                    self._carrier_action()
            self.next_restart, self.context = None, None
            self._emit(PeriodEndEvent)

    def _substitutions(self) -> None:
        if self.period != 2:
            return
        for team in self.setup.team_ids:
            plan = self.sub_plan[team]
            while plan and plan[0] <= self.clock and self.subs_made[team] < self.setup.max_substitutions:
                plan.pop(0)
                candidates = [p for p in self.on_pitch[team] if self.pos[p] is not GK and p not in self.came_on]
                if not candidates:
                    break
                weights = [1.0 if self.pos[p] is DF else 3.0 for p in candidates]
                off = self.rng.choices(candidates, weights=weights)[0]
                options = [b for b in self.bench[team] if self.pos[b] is self.pos[off]]
                options = options or [b for b in self.bench[team] if self.pos[b] is not GK]
                if not options:
                    break
                on = self.rng.choice(options)
                self._emit(SubstitutionEvent, team_id=team, player_off_id=off, player_on_id=on)
                self.on_pitch[team][self.on_pitch[team].index(off)] = on
                self.bench[team].remove(on)
                self.came_on.add(on)
                self.subs_made[team] += 1
                self.clock += self.rng.randint(10, 25) * 1000

    def _take_restart(self) -> None:
        assert self.next_restart is not None
        rtype, team, (x, y) = self.next_restart
        self.next_restart = None
        lo, hi = RESTART_DELAY_S[rtype]
        self.clock += self.rng.randint(lo, hi) * 1000
        tx, _ = self._att(team, x, y)
        if rtype is RestartType.GOAL_KICK:
            taker = self.goalkeeper[team]
        elif rtype in (RestartType.KICKOFF, RestartType.CORNER_KICK):
            taker = self._pick(team, 100.0, outfield=True)
        else:
            taker = self._pick(team, tx, outfield=True)
        self._emit(RestartEvent, team_id=team, restart_type=rtype, player_id=taker,
                   location=PitchLocation(x=x, y=y))
        self.team, self.carrier, self.ball, self.context = team, taker, (x, y), rtype

    def _carrier_action(self) -> None:
        rng = self.rng
        team = self.team
        opp = self.setup.opponent_id(team)
        x, y = self._att(team, *self.ball)
        ctx, self.context = self.context, None
        if ctx is None and self.pos[self.carrier] is GK:
            ctx = KEEPER  # keeper in possession distributes; never tackled or fouled here
        opp_press = self._pressing(opp)
        here = self._loc(team, x, y)

        pressure = None
        if ctx in (None, RestartType.THROW_IN, RestartType.GOAL_KICK, KEEPER) and \
                rng.random() < PRESS_PROB[opp_press][_zone(x)]:
            presser = self._pick(opp, PITCH_LENGTH_M - x, outfield=True)
            duration = rng.randint(400, 2500)
            pressure = self._emit(PressureEvent, team_id=opp, player_id=presser,
                                  opponent_player_id=self.carrier, location=here, duration_ms=duration)
            self.clock += duration // 2

        if ctx is None:
            defender = pressure.player_id if pressure else None
            related = pressure.event_id if pressure else None
            in_box = x > 88.5 and abs(y - 34) < 20.16
            if not in_box and rng.random() < FOUL_BASE + (FOUL_PRESSED if pressure else 0):
                fouler = defender or self._pick(opp, PITCH_LENGTH_M - x, outfield=True)
                self._emit(FoulEvent, team_id=opp, player_id=fouler, opponent_player_id=self.carrier,
                           location=here, related_event_id=related)
                self._restart(RestartType.FREE_KICK, team, (here.x, here.y))
                self.clock += 500
                return
            if rng.random() < TACKLE_BASE + (TACKLE_PRESSED if pressure else 0):
                tackler = defender or self._pick(opp, PITCH_LENGTH_M - x, outfield=True)
                won = rng.random() < TACKLE_WIN
                tackle = self._emit(TackleEvent, team_id=opp, player_id=tackler,
                                    opponent_player_id=self.carrier, location=here,
                                    outcome=TackleOutcome.WON if won else TackleOutcome.LOST,
                                    related_event_id=related)
                self.clock += rng.randint(500, 1500)
                if won:
                    self._emit(PossessionChangeEvent, team_id=opp, previous_team_id=team,
                               cause=PossessionChangeCause.TACKLE, player_id=tackler, location=here,
                               related_event_id=tackle.event_id)
                    self.team, self.carrier = opp, tackler
                    return

        if self._wants_shot(x, y, ctx):
            self._shoot(team, opp, x, y, ctx)
        else:
            self._pass(team, opp, x, y, ctx, pressure, opp_press)

    def _wants_shot(self, x: float, y: float, ctx: str | None) -> bool:
        r = self.rng.random()
        if ctx == CROSS:
            return r < 0.4
        if ctx == REBOUND:
            return r < 0.45
        if ctx == RestartType.FREE_KICK:
            return x > 75 and abs(y - 34) < 20 and r < 0.25
        if ctx is not None or x < 75:
            return False
        return r < SHOT_SCALE * math.exp(-math.hypot(PITCH_LENGTH_M - x, 34 - y) / 10)

    def _shoot(self, team: str, opp: str, x: float, y: float, ctx: str | None) -> None:
        rng = self.rng
        distance = math.hypot(PITCH_LENGTH_M - x, 34 - y)
        headed = ctx == CROSS and rng.random() < 0.6
        body = BodyPart.HEAD if headed else rng.choices(
            [BodyPart.RIGHT_FOOT, BodyPart.LEFT_FOOT, BodyPart.OTHER], weights=[0.62, 0.33, 0.05])[0]
        p_goal = min(0.6, 0.42 * math.exp(-distance / 9)) * (0.45 if headed else 1.0)
        if ctx == RestartType.FREE_KICK:
            p_goal *= 0.6
        if rng.random() < p_goal:
            outcome = ShotOutcome.GOAL
        else:
            outcome = rng.choices([ShotOutcome.SAVED, ShotOutcome.OFF_TARGET, ShotOutcome.BLOCKED,
                                   ShotOutcome.WOODWORK], weights=[0.30, 0.42, 0.25, 0.03])[0]
        shot = self._emit(ShotEvent, team_id=team, player_id=self.carrier, location=self._loc(team, x, y),
                          outcome=outcome, body_part=body)
        self.clock += 1500
        corner_spot = self._loc(team, PITCH_LENGTH_M, 0.0 if y < 34 else PITCH_WIDTH_M)

        if outcome is ShotOutcome.GOAL:
            self.score[team] += 1
            self._restart(RestartType.KICKOFF, opp, CENTRE_SPOT)
            self.clock += rng.randint(45, 80) * 1000
        elif outcome in (ShotOutcome.OFF_TARGET, ShotOutcome.WOODWORK):
            self._restart(RestartType.GOAL_KICK, opp, self._goal_kick_spot(opp))
        elif outcome is ShotOutcome.SAVED and rng.random() < 0.45:
            keeper = self.goalkeeper[opp]
            catch = self._loc(team, 103.5, 34 + rng.uniform(-3, 3))
            self._emit(PossessionChangeEvent, team_id=opp, previous_team_id=team, cause=PossessionChangeCause.SHOT,
                       player_id=keeper, location=catch, related_event_id=shot.event_id)
            self.team, self.carrier, self.ball, self.context = opp, keeper, (catch.x, catch.y), KEEPER
            self.clock += rng.randint(3000, 8000)
        elif outcome is ShotOutcome.SAVED:
            self._restart(RestartType.CORNER_KICK, team, (corner_spot.x, corner_spot.y))
        else:  # blocked
            r = rng.random()
            if r < 0.45:
                self._restart(RestartType.CORNER_KICK, team, (corner_spot.x, corner_spot.y))
            elif r < 0.85:
                blocker = self._pick(opp, PITCH_LENGTH_M - x, outfield=True)
                here = self._loc(team, x + 1.5, y)
                self._emit(PossessionChangeEvent, team_id=opp, previous_team_id=team,
                           cause=PossessionChangeCause.SHOT, player_id=blocker, location=here,
                           related_event_id=shot.event_id)
                self.team, self.carrier, self.ball = opp, blocker, (here.x, here.y)
            else:
                self.carrier = self._pick(team, x, exclude=(self.carrier,), outfield=True)
                here = self._loc(team, _clamp(x - rng.uniform(2, 8), 53, 104), _clamp(y + rng.gauss(0, 5), 1, 67))
                self.ball, self.context = (here.x, here.y), REBOUND
                self.clock += 1000

    def _wants_back_pass(self, x: float, ctx: str | None, pressured: bool) -> bool:
        probs = BACK_PASS_PROB.get(self.pos[self.carrier])
        if ctx is not None or probs is None or x > BACK_PASS_MAX_X:
            return False
        return self.rng.random() < probs[pressured]

    def _pass_target(self, x: float, y: float, ctx: str | None, pressured: bool) -> tuple[float, float, float | None, bool]:
        """Return (end_x, end_y, fixed completion prob or None for the open-play model, is_cross)."""
        rng = self.rng
        if ctx == RestartType.KICKOFF:
            return x - rng.uniform(6, 14), y + rng.uniform(-8, 8), 0.97, False
        if ctx == RestartType.CORNER_KICK or (ctx == RestartType.FREE_KICK and x > 70):
            return rng.uniform(93, 101), rng.uniform(26, 42), 0.33, True
        if ctx is None and x > 85 and (y < 14 or y > 54) and rng.random() < 0.35:
            return rng.uniform(92, 101), rng.uniform(27, 41), 0.28, True
        if ctx == RestartType.THROW_IN:
            return x + rng.gauss(3, 6), y + (1 if y < 34 else -1) * rng.uniform(5, 16), 0.86, False
        if ctx in (RestartType.GOAL_KICK, KEEPER):
            if rng.random() < KEEPER_LONG_PROB[pressured]:
                return x + rng.uniform(35, 60), rng.uniform(10, 58), 0.5, False
            return x + rng.uniform(6, 18), y + rng.uniform(-15, 15), 0.93, False
        zone = _zone(x)
        if rng.random() < (0.12 if pressured and zone == 0 else 0.06):
            return x + rng.gauss(32, 8), y + rng.gauss(0, 15), None, False
        mean = (7.0, 5.0, 1.0)[zone] - (3.0 if pressured else 0.0)
        return x + rng.gauss(mean, (11, 11, 9)[zone]), y + rng.gauss((34 - y) * 0.15, 11), None, False

    def _pass(self, team: str, opp: str, x: float, y: float, ctx: str | None,
              pressure: MatchEvent | None, opp_press: PressingIntensity) -> None:
        rng = self.rng
        keeper = self.goalkeeper[team]
        back_pass = self._wants_back_pass(x, ctx, pressure is not None)
        if back_pass:
            ex, ey, p_fixed, is_cross = rng.uniform(4, 12), 34 + rng.gauss(0, 7), 0.96, False
        else:
            ex, ey, p_fixed, is_cross = self._pass_target(x, y, ctx, pressure is not None)
        ex, ey = _clamp(ex, 1, 104), _clamp(ey, 1, 67)
        distance = math.hypot(ex - x, ey - y)
        if p_fixed is None:
            p = 0.92 - 0.007 * max(0.0, distance - 12) - (0.08 if ex > 70 else 0.0) + (0.04 if ex < x - 2 else 0.0)
        else:
            p = p_fixed
        if pressure is not None:
            p -= PRESSED_PASS_PENALTY[opp_press]
        p = _clamp(p, 0.1, 0.98)
        duration = int(600 + distance * 60)
        start = self._loc(team, x, y)
        common = dict(team_id=team, player_id=self.carrier, location=start,
                      related_event_id=pressure.event_id if pressure else None)

        p_out = 0.0 if ctx == RestartType.KICKOFF else 0.034 + (0.02 if pressure else 0.0)
        if rng.random() < p_out:
            if ex > 98:
                end = self._loc(team, PITCH_LENGTH_M, ey)
                self._restart(RestartType.GOAL_KICK, opp, self._goal_kick_spot(opp))
            else:
                end = self._loc(team, ex, 0.0 if ey < 34 else PITCH_WIDTH_M)
                self._restart(RestartType.THROW_IN, opp, (end.x, end.y))
            self._emit(PassEvent, **common, end_location=end, outcome=PassOutcome.OUT_OF_PLAY)
            self.clock += duration
            return

        end = self._loc(team, ex, ey)
        if not is_cross and p_fixed is None and ex - x > 8 and ex > 70 and rng.random() < 0.03:
            self._emit(PassEvent, **common, end_location=end, outcome=PassOutcome.OFFSIDE)
            self._restart(RestartType.FREE_KICK, opp, (end.x, end.y))
            self.clock += duration
            return

        if rng.random() < p:
            recipient = keeper if back_pass else self._pick(team, ex, exclude=(self.carrier,), outfield=True)
            self._emit(PassEvent, **common, end_location=end, outcome=PassOutcome.COMPLETE, recipient_id=recipient)
            self.carrier = recipient
            self.clock += duration
            if is_cross:
                self.ball, self.context = (end.x, end.y), CROSS
                self.clock += 300
                return
            cx = ex + max(-3.0, rng.gauss(2.5 if ex < 85 else 0.5, 3))
            if pressure is not None and opp_press is HIGH and ex - x > 15:
                cx += rng.uniform(4, 10)  # space left behind an aggressive press
            carry = self._loc(team, _clamp(cx, 1, 103.5), _clamp(ey + rng.gauss(0, 3), 1, 67))
            self.ball = (carry.x, carry.y)
            self.clock += rng.randint(800, 3500)
            return

        pass_event = self._emit(PassEvent, **common, end_location=end, outcome=PassOutcome.INCOMPLETE)
        self.clock += duration
        opp_x = PITCH_LENGTH_M - ex
        if is_cross and rng.random() < CROSS_CLEARED_FOR_CORNER:
            self._clear_for_corner(team, opp, ex, ey, end)
            return
        if rng.random() < INTERCEPT_SHARE:
            gainer = self._pick(opp, opp_x, outfield=True)
            cause = PossessionChangeCause.INTERCEPTION
            related = self._emit(InterceptionEvent, team_id=opp, player_id=gainer, location=end).event_id
        else:
            gainer = self._pick(opp, opp_x)
            cause, related = PossessionChangeCause.INCOMPLETE_PASS, pass_event.event_id
        self._emit(PossessionChangeEvent, team_id=opp, previous_team_id=team, cause=cause, player_id=gainer,
                   location=end, related_event_id=related)
        self.team, self.carrier, self.ball = opp, gainer, (end.x, end.y)
        self.clock += rng.randint(500, 1500)

    def _clear_for_corner(self, team: str, opp: str, ex: float, ey: float, end: PitchLocation) -> None:
        """A defender cuts out a cross and clears it behind their own goal line."""
        rng = self.rng
        defender = self._pick(opp, PITCH_LENGTH_M - ex, outfield=True)
        cut_out = self._emit(InterceptionEvent, team_id=opp, player_id=defender, location=end)
        self._emit(PossessionChangeEvent, team_id=opp, previous_team_id=team,
                   cause=PossessionChangeCause.INTERCEPTION, player_id=defender, location=end,
                   related_event_id=cut_out.event_id)
        behind = self._loc(team, PITCH_LENGTH_M, _clamp(ey + rng.gauss(0, 8), 1, 67))
        self._emit(PassEvent, team_id=opp, player_id=defender, location=end, end_location=behind,
                   outcome=PassOutcome.OUT_OF_PLAY, related_event_id=cut_out.event_id)
        self.team = opp
        self.clock += rng.randint(500, 1200)
        corner = self._loc(team, PITCH_LENGTH_M, 0.0 if ey < 34 else PITCH_WIDTH_M)
        self._restart(RestartType.CORNER_KICK, team, (corner.x, corner.y))


def simulate_match(seed: int, script: InterventionManifest | None = None) -> SimulationResult:
    """Simulate one full match. Same seed and script => identical output."""
    setup = build_match_setup(match_id_for_seed(seed))
    if script is None:
        script = pressing_switch_script(setup, seed)
    if script.match_id != setup.match_id or script.simulation_seed != seed:
        raise ValueError("script does not belong to this seed's match")
    engine = _Engine(setup, script)
    engine.run()
    events = tuple(engine.events)
    tracker = validate_match(setup, events)  # never emit an invalid stream
    if tracker.score != engine.score:
        raise AssertionError("engine score disagrees with the event stream")
    ground_truth = GroundTruthRecord(simulator_version=SIMULATOR_VERSION, script=script,
                                     applied=tuple(engine.applied.values()), final_score=dict(engine.score))
    return SimulationResult(setup=setup, events=events, ground_truth=ground_truth)
