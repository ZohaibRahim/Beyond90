"""Benchmark scoring and configuration selection (docs/EVALUATION_PROTOCOL.md sections 3-7)."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import cache

from beyond90.detection import DetectorConfig, Direction, EvidenceStatus, RollingState, detect
from beyond90.detection.detector import DetectionResult
from beyond90.schemas import MatchEvent, MatchSetup, PeriodEndEvent
from beyond90.simulator import SimulationResult, control_script, simulate_match

MINUTE_MS = 60_000
WITHIN_MS = 15 * MINUTE_MS

CANDIDATES: dict[str, DetectorConfig] = {
    "original": DetectorConfig(),
    "recent12": DetectorConfig(min_recent_buildup=12, min_half_buildup=5),
    "recent10": DetectorConfig(min_recent_buildup=10, min_half_buildup=4),
    "recent10_base30": DetectorConfig(min_recent_buildup=10, min_half_buildup=4,
                                      min_baseline_ms=15 * MINUTE_MS, min_baseline_buildup=30),
    "recent8": DetectorConfig(min_recent_buildup=8, min_half_buildup=3),
}
# Most to least conservative (protocol section 7).
CONSERVATIVE_ORDER = ("original", "recent12", "recent10", "recent10_base30", "recent8")
MAX_CONTROL_FA_PER_MATCH = 0.10
MAX_EARLY = 1
MIN_EXTRA_CORRECT = 2
MIN_DELAY_GAIN_MS = 2 * MINUTE_MS

IE_REASONS = {
    "baseline period shorter": "baseline_length",
    "baseline build-up passes": "baseline_buildup",
    "recent build-up passes": "recent_buildup",
    "5-minute half": "half_buildup",
}


@cache
def simulate_pair(seed: int) -> tuple[SimulationResult, SimulationResult]:
    treated = simulate_match(seed)
    return treated, simulate_match(seed, control_script(treated.ground_truth.script))


def _public(result: SimulationResult) -> tuple[MatchSetup, tuple[MatchEvent, ...]]:
    """The only parts of a simulation the detector may see."""
    return result.setup, tuple(result.events)


def _period_ends(events: Sequence[MatchEvent]) -> dict[int, int]:
    return {e.period: e.clock_ms for e in events if isinstance(e, PeriodEndEvent)}


def switch_elapsed_ms(treated: SimulationResult) -> int:
    """T0: elapsed time of the first event the intervention affected (hidden; harness only)."""
    applied = treated.ground_truth.applied[0]
    event = next(e for e in treated.events if e.event_id == applied.first_event_id)
    return event.clock_ms + (0 if event.period == 1 else _period_ends(treated.events)[1])


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


@dataclass
class PairScore:
    seed: int
    switch_ms: int
    outcome: str  # correct | early | miss
    detected_ms: int | None
    treated_false_alarms: int
    control_false_alarms: int
    team_ticks: int
    insufficient_ticks: int
    target_post_ticks: int
    target_post_insufficient: int
    ie_reasons: Counter = field(default_factory=Counter)
    opportunity_per_10min: float = 0.0

    @property
    def delay_ms(self) -> int | None:
        return None if self.outcome != "correct" else self.detected_ms - self.switch_ms


def score_pair(seed: int, config: DetectorConfig) -> PairScore:
    treated, control = simulate_pair(seed)
    target = treated.ground_truth.script.interventions[0].team_id
    t0 = switch_elapsed_ms(treated)
    res_t: DetectionResult = detect(*_public(treated), config=config)
    res_c: DetectionResult = detect(*_public(control), config=config)

    target_findings = [f for f in res_t.findings if f.team_id == target and f.direction is Direction.INCREASE]
    detected = target_findings[0].detected_elapsed_ms if target_findings else None
    outcome = "miss" if detected is None else ("correct" if detected >= t0 else "early")

    ticks = res_t.assessments + res_c.assessments
    post = [a for a in res_t.assessments if a.team_id == target and a.elapsed_ms >= t0]
    post_ie = [a for a in post if a.status is EvidenceStatus.INSUFFICIENT_EVIDENCE]
    reasons = Counter(label for a in post_ie for text, label in IE_REASONS.items() if text in a.reason)

    state = RollingState(treated.setup)
    for e in treated.events:
        state.ingest(e)
    ends = _period_ends(treated.events)
    full_time = ends[1] + ends[2]
    buildup = state.window(target, t0, full_time + 1).opp_buildup_passes
    return PairScore(
        seed=seed, switch_ms=t0, outcome=outcome, detected_ms=detected,
        treated_false_alarms=len(res_t.findings) - len(target_findings),
        control_false_alarms=len(res_c.findings),
        team_ticks=len(ticks),
        insufficient_ticks=sum(a.status is EvidenceStatus.INSUFFICIENT_EVIDENCE for a in ticks),
        target_post_ticks=len(post), target_post_insufficient=len(post_ie), ie_reasons=reasons,
        opportunity_per_10min=buildup / ((full_time - t0) / (10 * MINUTE_MS)),
    )


@dataclass
class ConfigSummary:
    name: str
    config: DetectorConfig
    scores: list[PairScore]

    @property
    def n(self) -> int:
        return len(self.scores)

    def count(self, outcome: str) -> int:
        return sum(s.outcome == outcome for s in self.scores)

    @property
    def correct(self) -> int:
        return self.count("correct")

    @property
    def correct_within(self) -> int:
        return sum(s.outcome == "correct" and s.delay_ms <= WITHIN_MS for s in self.scores)

    @property
    def delays_min(self) -> list[float]:
        return [s.delay_ms / MINUTE_MS for s in self.scores if s.delay_ms is not None]

    @property
    def median_delay_min(self) -> float | None:
        return statistics.median(self.delays_min) if self.delays_min else None

    @property
    def control_fa(self) -> int:
        return sum(s.control_false_alarms for s in self.scores)

    @property
    def control_matches_with_fa(self) -> int:
        return sum(s.control_false_alarms > 0 for s in self.scores)

    @property
    def treated_fa(self) -> int:
        return sum(s.treated_false_alarms for s in self.scores)

    @property
    def insufficient_pct(self) -> float:
        return 100 * sum(s.insufficient_ticks for s in self.scores) / sum(s.team_ticks for s in self.scores)

    @property
    def target_post_insufficient_pct(self) -> float:
        return 100 * sum(s.target_post_insufficient for s in self.scores) / sum(
            s.target_post_ticks for s in self.scores)

    def reason_pct(self) -> dict[str, float]:
        total = sum(s.target_post_ticks for s in self.scores)
        counts = sum((s.ie_reasons for s in self.scores), Counter())
        return {label: 100 * counts[label] / total for label in IE_REASONS.values()}

    @property
    def eligible(self) -> bool:
        return self.control_fa <= MAX_CONTROL_FA_PER_MATCH * self.n and self.count("early") <= MAX_EARLY


def run_configs(seeds: Iterable[int], configs: dict[str, DetectorConfig] = CANDIDATES) -> list[ConfigSummary]:
    seeds = tuple(seeds)
    return [ConfigSummary(name, cfg, [score_pair(s, cfg) for s in seeds]) for name, cfg in configs.items()]


def select(summaries: Sequence[ConfigSummary], order: Sequence[str] = CONSERVATIVE_ORDER) -> str | None:
    """Protocol section 7. Returns the proposed configuration name, or None if none is eligible."""
    by_name = {s.name: s for s in summaries}
    eligible = [by_name[n] for n in order if n in by_name and by_name[n].eligible]
    if not eligible:
        return None
    choice = eligible[0]
    for cand in eligible[1:]:
        more_correct = cand.correct >= choice.correct + MIN_EXTRA_CORRECT
        cd, ch = cand.median_delay_min, choice.median_delay_min
        faster = (cand.correct >= choice.correct and cd is not None
                  and (ch is None or cd <= ch - MIN_DELAY_GAIN_MS / MINUTE_MS))
        if more_correct or faster:
            choice = cand
    return choice.name


def opportunity_thirds(scores: Sequence[PairScore]) -> tuple[float, float]:
    rates = sorted(s.opportunity_per_10min for s in scores)
    q = statistics.quantiles(rates, n=3)
    return q[0], q[1]
