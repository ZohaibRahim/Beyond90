"""Deterministic detector for sustained changes in a team's pressing.

At every evaluation tick (each whole minute of each period) and for each team,
the detector compares the last 10 minutes with that team's own earlier baseline
(kickoff up to the start of the recent window), using only events released by the
tick (see ``beyond90.live.feed``).

Decision rule (all thresholds fixed in ``DetectorConfig`` before any evaluation
run, from statistical conventions and football reasoning, NOT tuned against
hidden ground truth):

1. Enough data: baseline >= 20 min and >= 40 opposition build-up passes; recent
   window >= 15 build-up passes, and >= 6 in each 5-minute half. Otherwise
   INSUFFICIENT_EVIDENCE.
2. Primary signal: high pressures per opposition build-up pass, recent vs baseline,
   conditional binomial rate test |z| >= 2.33 (one-sided 1%) AND a rate ratio of
   at least 1.5 (or at most 1/1.5 for a decrease).
3. Not a spike: BOTH 5-minute halves of the recent window must each move in the
   same direction by a ratio of at least 1.2.
4. Corroboration: at least one independent supporting signal moves the expected
   way with z >= 1.64: high regains per build-up pass (same direction),
   opposition defensive-third completion (opposite direction), opposition
   long-pass share (same direction).
5. Persistence: rules 2–4 must hold on 3 consecutive ticks -> SUSTAINED_CHANGE.
   If only the primary signal holds -> CANDIDATE. Otherwise NO_CHANGE.

Statistical caveat: the z values are approximate detection heuristics, NOT calibrated
probabilities. Counts are not independent Poisson/binomial draws (passes and pressures
cluster within possessions), the baseline is chosen by the clock rather than at random,
and consecutive ticks share up to 9 of their 10 recent minutes, so successive
assessments are strongly dependent and "3 consecutive ticks" is far weaker evidence
than three independent tests. Repeating the test every minute for two teams and two
directions also inflates the chance of a spurious finding. Error rates must therefore
be measured empirically (paired control matches; docs/EVALUATION_PROTOCOL.md), not
read off the thresholds.

A finding is emitted the first time a team reaches SUSTAINED_CHANGE in a
direction. Its ``supporting_event_ids`` are the headline events (high pressures and
high regains in the recent window); the complete numerator and denominator events
for every window are available on demand from ``detection.evidence.finding_evidence``. Findings report observed associations in public events, never causes
of individual passes, turnovers or goals.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from beyond90.detection.metrics import RollingState, WindowMetrics
from beyond90.live.feed import AsOfFeed, MatchTime
from beyond90.schemas import MatchEvent, MatchSetup, PeriodEndEvent

MINUTE_MS = 60_000


@dataclass(frozen=True)
class DetectorConfig:
    long_window_ms: int = 10 * MINUTE_MS
    short_window_ms: int = 5 * MINUTE_MS
    min_baseline_ms: int = 20 * MINUTE_MS
    min_baseline_buildup: int = 40
    min_recent_buildup: int = 15
    min_half_buildup: int = 6
    z_primary: float = 2.33
    min_rate_ratio: float = 1.5
    min_half_ratio: float = 1.2
    z_support: float = 1.64
    persistence_ticks: int = 3


DEFAULT_CONFIG = DetectorConfig()


class EvidenceStatus(StrEnum):
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NO_CHANGE = "no_change"
    CANDIDATE = "candidate"
    SUSTAINED_CHANGE = "sustained_change"


class Direction(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Assessment(_Model):
    team_id: str
    period: int
    clock_ms: int
    elapsed_ms: int
    status: EvidenceStatus
    direction: Direction | None = None
    reason: str
    metrics: dict[str, float | int | None]


class Finding(_Model):
    finding_type: str = "pressing_change"
    team_id: str
    direction: Direction
    status: EvidenceStatus
    detected_period: int
    detected_clock_ms: int
    detected_elapsed_ms: int
    evidence_window_start_ms: int
    evidence_window_end_ms: int
    metrics: dict[str, float | int | None]
    supporting_event_ids: tuple[str, ...]
    statement: str


class DetectionResult(_Model):
    match_id: str
    config: dict[str, float | int]
    assessments: tuple[Assessment, ...]
    findings: tuple[Finding, ...]


def rate_z(k1: float, n1: float, k0: float, n0: float) -> float:
    """Conditional binomial test for two event rates per unit exposure; z > 0 means recent is higher."""
    total = k1 + k0
    if total == 0 or n1 <= 0 or n0 <= 0:
        return 0.0
    f = n1 / (n1 + n0)
    sd = math.sqrt(total * f * (1 - f))
    return (k1 - total * f) / sd if sd > 0 else 0.0


def proportion_z(k1: float, n1: float, k0: float, n0: float) -> float:
    """Two-proportion z test (pooled); z > 0 means recent proportion is higher."""
    if n1 <= 0 or n0 <= 0:
        return 0.0
    p = (k1 + k0) / (n1 + n0)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n0))
    return (k1 / n1 - k0 / n0) / se if se > 0 else 0.0


def _rate(k: float, n: float) -> float:
    return k / n if n else 0.0


@dataclass
class _TeamTrack:
    streak: dict[Direction, int]
    reported: set[Direction]


class PressingChangeDetector:
    def __init__(self, setup: MatchSetup, config: DetectorConfig = DEFAULT_CONFIG) -> None:
        self.setup = setup
        self.config = config
        self.state = RollingState(setup)
        self.tracks = {t: _TeamTrack({d: 0 for d in Direction}, set()) for t in setup.team_ids}
        self.assessments: list[Assessment] = []
        self.findings: list[Finding] = []

    def ingest(self, events: Sequence[MatchEvent]) -> None:
        for e in events[self.state.ingested:]:
            self.state.ingest(e)

    def evaluate(self, at: MatchTime) -> None:
        now = self.state.elapsed_ms(at.period, at.clock_ms)
        if now is None:
            return
        for team in self.setup.team_ids:
            assessment, finding = self._evaluate_team(team, at, now)
            self.assessments.append(assessment)
            if finding is not None:
                self.findings.append(finding)

    def _evaluate_team(self, team: str, at: MatchTime, now: int) -> tuple[Assessment, Finding | None]:
        c, st, track = self.config, self.state, self.tracks[team]
        recent_start, half = now - c.long_window_ms, now - c.short_window_ms
        # Each window displays rates down to the gate the decision applies to it.
        base = st.window(team, 0, recent_start, c.min_baseline_buildup)
        recent = st.window(team, recent_start, now, c.min_recent_buildup)
        h1 = st.window(team, recent_start, half, c.min_half_buildup)
        h2 = st.window(team, half, now, c.min_half_buildup)
        metrics = {f"recent_{k}": v for k, v in recent.as_dict().items()}
        metrics |= {f"baseline_{k}": v for k, v in base.as_dict().items()}

        def assess(status, reason, direction=None, extra=None):
            # Persistence counts consecutive ticks meeting every condition in one direction.
            for d in Direction:
                if not (status in (EvidenceStatus.CANDIDATE, EvidenceStatus.SUSTAINED_CHANGE)
                        and d is direction and extra is not None and extra.get("all_conditions")):
                    track.streak[d] = 0
            return Assessment(team_id=team, period=at.period, clock_ms=at.clock_ms, elapsed_ms=now,
                              status=status, direction=direction, reason=reason, metrics=metrics | (extra or {}))

        if recent_start < c.min_baseline_ms:
            return assess(EvidenceStatus.INSUFFICIENT_EVIDENCE, "baseline period shorter than 20 minutes"), None
        shortfalls = []
        if base.opp_buildup_passes < c.min_baseline_buildup:
            shortfalls.append(f"baseline build-up passes {base.opp_buildup_passes} < {c.min_baseline_buildup}")
        if recent.opp_buildup_passes < c.min_recent_buildup:
            shortfalls.append(f"recent build-up passes {recent.opp_buildup_passes} < {c.min_recent_buildup}")
        if min(h1.opp_buildup_passes, h2.opp_buildup_passes) < c.min_half_buildup:
            shortfalls.append(f"a 5-minute half has fewer than {c.min_half_buildup} build-up passes")
        if shortfalls:
            return assess(EvidenceStatus.INSUFFICIENT_EVIDENCE, "; ".join(shortfalls)), None

        z = rate_z(recent.high_pressures, recent.opp_buildup_passes, base.high_pressures, base.opp_buildup_passes)
        direction = Direction.INCREASE if z > 0 else Direction.DECREASE
        sign = 1 if direction is Direction.INCREASE else -1
        base_rate = _rate(base.high_pressures, base.opp_buildup_passes)
        recent_rate = _rate(recent.high_pressures, recent.opp_buildup_passes)
        ratio = recent_rate / base_rate if base_rate > 0 else (math.inf if recent_rate > 0 else 1.0)

        def moved(r: float, factor: float) -> bool:
            if base_rate == 0:
                return sign > 0 and r > 0
            return r / base_rate >= factor if sign > 0 else r / base_rate <= 1 / factor

        primary = abs(z) >= c.z_primary and moved(recent_rate, c.min_rate_ratio)
        halves = all(moved(_rate(h.high_pressures, h.opp_buildup_passes), c.min_half_ratio) for h in (h1, h2))
        support = {
            "high_regains_z": rate_z(recent.high_regains, recent.opp_buildup_passes,
                                     base.high_regains, base.opp_buildup_passes),
            "opp_defensive_third_completion_z": proportion_z(
                recent.opp_buildup_completed, recent.opp_buildup_passes,
                base.opp_buildup_completed, base.opp_buildup_passes),
            "opp_long_pass_share_z": proportion_z(recent.opp_long_passes, recent.opp_passes,
                                                  base.opp_long_passes, base.opp_passes),
        }
        expected_sign = {"high_regains_z": sign, "opp_defensive_third_completion_z": -sign,
                         "opp_long_pass_share_z": sign}
        corroborating = [k for k, v in support.items() if v * expected_sign[k] >= c.z_support]
        extra = {"primary_z": round(z, 3), "rate_ratio": None if math.isinf(ratio) else round(ratio, 3),
                 "half1_rate": round(_rate(h1.high_pressures, h1.opp_buildup_passes), 4),
                 "half2_rate": round(_rate(h2.high_pressures, h2.opp_buildup_passes), 4),
                 **{k: round(v, 3) for k, v in support.items()},
                 "corroborating_signals": len(corroborating)}

        if not primary:
            return assess(EvidenceStatus.NO_CHANGE, f"primary signal not met (z={z:.2f}, ratio={ratio:.2f})",
                          extra=extra), None
        if not (halves and corroborating):
            missing = [m for m, ok in (("both 5-minute halves", halves), ("a corroborating signal", corroborating))
                       if not ok]
            return assess(EvidenceStatus.CANDIDATE, "primary signal met; missing " + " and ".join(missing),
                          direction, extra), None

        extra["all_conditions"] = 1
        track.streak[direction] += 1
        if track.streak[direction] < c.persistence_ticks:
            return assess(EvidenceStatus.CANDIDATE,
                          f"all conditions met for {track.streak[direction]}/{c.persistence_ticks} ticks",
                          direction, extra), None
        a = assess(EvidenceStatus.SUSTAINED_CHANGE, "sustained change: all conditions met on "
                   f"{track.streak[direction]} consecutive ticks; corroborated by {', '.join(corroborating)}",
                   direction, extra)
        if direction in track.reported:
            return a, None
        track.reported.add(direction)
        ids = st.event_ids(team, "high_pressures", recent_start, now) + st.event_ids(team, "high_regains",
                                                                                     recent_start, now)
        return a, self._finding(team, direction, at, now, recent_start, base, recent, metrics | extra, ids)

    def _finding(self, team: str, direction: Direction, at: MatchTime, now: int, start: int,
                 base: WindowMetrics, recent: WindowMetrics, metrics, ids: list[str]) -> Finding:
        name = self.setup.team(team).name
        opp = self.setup.team(self.setup.opponent_id(team)).name
        b, r = base.high_pressures_per_buildup_pass, recent.high_pressures_per_buildup_pass
        bc, rc = base.opp_defensive_third_completion, recent.opp_defensive_third_completion

        def f(v: float | None, pct: bool = False) -> str:
            return "n/a" if v is None else (f"{100 * v:.0f}%" if pct else f"{v:.2f}")

        def poss(n: str) -> str:
            return f"{n}'" if n.endswith("s") else f"{n}'s"

        statement = (
            f"Observed {direction} in {poss(name)} attacking-third pressing: pressures per {opp} build-up pass "
            f"went from {f(b)} ({base.high_pressures}/{base.opp_buildup_passes}, earlier in the match) to {f(r)} "
            f"({recent.high_pressures}/{recent.opp_buildup_passes}, last 10 minutes). Over the same period "
            f"{poss(opp)} defensive-third pass completion was {f(bc, True)} -> {f(rc, True)} and {name} won the ball "
            f"in its attacking third {recent.high_regains} times. This is an association between observed "
            f"event rates; it does not establish why it happened or that it caused any individual pass, "
            f"turnover or goal."
        )
        return Finding(team_id=team, direction=direction, status=EvidenceStatus.SUSTAINED_CHANGE,
                       detected_period=at.period, detected_clock_ms=at.clock_ms, detected_elapsed_ms=now,
                       evidence_window_start_ms=start, evidence_window_end_ms=now, metrics=metrics,
                       supporting_event_ids=tuple(ids), statement=statement)

    def result(self) -> DetectionResult:
        return DetectionResult(match_id=self.setup.match_id, config=vars(self.config),
                               assessments=tuple(self.assessments), findings=tuple(self.findings))


def evaluation_ticks(feed: AsOfFeed, until: MatchTime | None = None) -> list[MatchTime]:
    """Whole minutes of each period, while the period is (as far as is visible at that tick) still running."""
    ticks: list[MatchTime] = []
    for period in (1, 2):
        minute = 1
        while True:
            tick = MatchTime(period, minute * MINUTE_MS)
            if until is not None and tick > until:
                return ticks
            visible = feed.visible(tick)
            ended = [e for e in visible if isinstance(e, PeriodEndEvent) and e.period == period]
            if ended and ended[0].clock_ms < tick.clock_ms:
                break
            if not any(e.period == period for e in visible):
                return ticks  # period not under way (yet) in what is visible
            ticks.append(tick)
            minute += 1
            if minute > 70:  # safety bound: a period never lasts 70 minutes
                break
    return ticks


def detect(setup: MatchSetup, events: Sequence[MatchEvent], until: MatchTime | None = None,
           config: DetectorConfig = DEFAULT_CONFIG) -> DetectionResult:
    """Run the detector over a public stream, evaluating every tick up to ``until``.

    Each tick sees only ``AsOfFeed(events).visible(tick)``, so the result for any tick
    is unaffected by later events.
    """
    feed = AsOfFeed(events)
    detector = PressingChangeDetector(setup, config)
    for tick in evaluation_ticks(feed, until):
        detector.ingest(feed.visible(tick))
        detector.evaluate(tick)
    return detector.result()
