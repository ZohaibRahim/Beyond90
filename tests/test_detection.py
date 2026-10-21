import re
from functools import cache

import pytest

from beyond90.detection import (
    DEFAULT_CONFIG,
    DetectionResult,
    Direction,
    EvidenceStatus,
    PressingChangeDetector,
    RollingState,
    WindowMetrics,
    detect,
)
from beyond90.detection.detector import proportion_z, rate_z
from beyond90.live.feed import AsOfFeed, MatchTime, event_time, release_times
from beyond90.simulator import control_script, simulate_match
from streams import SETUP, Stream

# -- statistics ---------------------------------------------------------------------


def test_rate_z_basic():
    assert rate_z(10, 20, 10, 100) > 3       # recent rate 0.5 vs baseline 0.1
    assert rate_z(2, 20, 10, 100) == pytest.approx(0.0)
    assert rate_z(0, 20, 0, 100) == 0.0      # no events at all: no evidence
    assert rate_z(1, 0, 1, 10) == 0.0


def test_proportion_z_basic():
    assert proportion_z(5, 20, 85, 100) < -3  # completion 25% vs 85%
    assert proportion_z(0, 0, 5, 10) == 0.0


# -- rolling metrics on a hand-built stream -------------------------------------------

def test_rolling_metrics_definitions():
    # kes attacks toward x=0 in period 1, so kes's defensive third is x > 70 (fixed coordinates).
    s = Stream().kickoff("kes", "kes-09", clock_ms=1000)
    s.pass_("kes", "kes-09", "kes-04", start=(52.5, 34), end=(90, 34), clock_ms=2000)
    s.add("pressure", team_id="nbh", player_id="nbh-09", opponent_player_id="kes-04",
          location={"x": 90, "y": 34}, duration_ms=800, clock_ms=4000)
    s.pass_("kes", "kes-04", "kes-01", start=(90, 34), end=(100, 34), clock_ms=5000)  # build-up, to keeper
    s.pass_("kes", "kes-01", "kes-09", start=(100, 34), end=(55, 30), clock_ms=8000)  # keeper long ball
    s.pass_("kes", "kes-09", outcome="incomplete", start=(55, 30), end=(60, 30), clock_ms=11000)
    s.add("possession_change", team_id="nbh", previous_team_id="kes", cause="incomplete_pass",
          player_id="nbh-06", location={"x": 60, "y": 30}, clock_ms=12000)
    state = RollingState(SETUP)
    for e in s.events:
        state.ingest(e)
    w = state.window("nbh", 0, 60_000)
    assert (w.pressures, w.high_pressures) == (1, 1)
    assert w.opp_buildup_passes == 2 and w.opp_buildup_completed == 2  # passes from x=90 and x=100
    assert (w.opp_passes, w.opp_long_passes) == (4, 2)  # 37.5 m and 45.2 m
    assert (w.opp_keeper_passes, w.opp_keeper_long) == (1, 1)
    assert w.high_regains == 0  # regained at x=60 in nbh's frame
    assert w.high_pressures_per_buildup_pass is None  # denominator below minimum -> explicit None
    assert w.opp_controlled_min > 0
    assert state.window("kes", 0, 60_000).high_pressures == 0


# -- decision logic with scripted window metrics ----------------------------------------

def W(team, hp=0, bp=20, comp=None, regains=0, passes=60, longs=6):
    return WindowMetrics(team_id=team, start_ms=0, end_ms=0, pressures=hp, high_pressures=hp,
                         high_regains=regains, opp_buildup_passes=bp,
                         opp_buildup_completed=round(0.85 * bp) if comp is None else comp,
                         opp_passes=passes, opp_long_passes=longs, opp_keeper_passes=0, opp_keeper_long=0,
                         opp_controlled_min=5.0)


def _add(a: WindowMetrics, b: WindowMetrics) -> WindowMetrics:
    keys = ("pressures", "high_pressures", "high_regains", "opp_buildup_passes", "opp_buildup_completed",
            "opp_passes", "opp_long_passes", "opp_keeper_passes", "opp_keeper_long", "opp_controlled_min")
    return WindowMetrics(team_id=a.team_id, start_ms=0, end_ms=0, **{k: getattr(a, k) + getattr(b, k) for k in keys})


class StubState:
    """Stands in for RollingState: a scenario gives (baseline, first 5-min half, second 5-min half)."""

    def __init__(self, scenario):
        self.scenario = scenario
        self.ingested = 0

    def elapsed_ms(self, period, clock_ms):
        return clock_ms

    def window(self, team, start, end):
        base, h1, h2 = self.scenario(team)
        if start == 0:
            return base
        if end - start == DEFAULT_CONFIG.long_window_ms:
            return _add(h1, h2)
        return h2 if end - start == DEFAULT_CONFIG.short_window_ms and end % 60_000 == 0 and \
            start == end - DEFAULT_CONFIG.short_window_ms and self._second(start, end) else h1

    def _second(self, start, end):
        return getattr(self, "_now", None) == end

    def event_ids(self, team, key, start, end):
        return [f"{team}-{key}-{start}"]


def run_ticks(scenario, minutes):
    d = PressingChangeDetector(SETUP)
    stub = StubState(scenario)
    d.state = stub
    for m in minutes:
        stub._now = m * 60_000
        d.evaluate(MatchTime(1, m * 60_000))
    return d


def steady(team):
    return W(team, hp=10, bp=100), W(team, hp=1, bp=10), W(team, hp=1, bp=10)


def pressing_up(team):
    if team != "kes":
        return steady(team)
    half = W(team, hp=5, bp=10, comp=5, regains=2)  # rate 0.5 vs 0.1; completion 50% vs 85%
    return W(team, hp=10, bp=100), half, half


def spike(team):
    if team != "kes":
        return steady(team)
    return W(team, hp=10, bp=100), W(team, hp=9, bp=10, comp=5, regains=2), W(team, hp=0, bp=10)


def uncorroborated(team):
    if team != "kes":
        return steady(team)
    half = W(team, hp=5, bp=10)  # pressure up; completion, regains and long passes unchanged
    return W(team, hp=10, bp=100), half, half


def thin(team):
    return W(team, hp=10, bp=100), W(team, hp=5, bp=3), W(team, hp=5, bp=3)


def statuses(d, team="kes"):
    return [a.status for a in d.assessments if a.team_id == team]


def test_stub_returns_distinct_halves():
    stub = StubState(spike)
    stub._now = 40 * 60_000
    assert stub.window("kes", 30 * 60_000, 35 * 60_000).high_pressures == 9
    assert stub.window("kes", 35 * 60_000, 40 * 60_000).high_pressures == 0


def test_sustained_change_needs_three_consecutive_ticks_and_reports_once():
    d = run_ticks(pressing_up, range(31, 37))
    assert statuses(d) == [EvidenceStatus.CANDIDATE] * 2 + [EvidenceStatus.SUSTAINED_CHANGE] * 4
    assert len(d.findings) == 1
    f = d.findings[0]
    assert (f.team_id, f.direction, f.detected_clock_ms) == ("kes", Direction.INCREASE, 33 * 60_000)
    assert f.supporting_event_ids and f.metrics["corroborating_signals"] >= 1
    assert set(statuses(d, "nbh")) == {EvidenceStatus.NO_CHANGE}


def test_isolated_spike_is_not_declared():
    d = run_ticks(spike, range(31, 41))
    assert set(statuses(d)) == {EvidenceStatus.CANDIDATE}
    assert all("both 5-minute halves" in a.reason for a in d.assessments if a.team_id == "kes")
    assert not d.findings


def test_uncorroborated_pressure_rise_stays_candidate():
    d = run_ticks(uncorroborated, range(31, 41))
    assert set(statuses(d)) == {EvidenceStatus.CANDIDATE} and not d.findings


def test_sparse_denominators_give_insufficient_evidence():
    d = run_ticks(thin, range(31, 41))
    assert set(statuses(d)) == {EvidenceStatus.INSUFFICIENT_EVIDENCE}
    assert "build-up passes" in d.assessments[0].reason


def test_too_early_is_insufficient_evidence():
    d = run_ticks(pressing_up, range(1, 30))
    assert set(statuses(d)) == {EvidenceStatus.INSUFFICIENT_EVIDENCE}


def test_decrease_is_detected_symmetrically():
    def pressing_down(team):
        if team != "kes":
            return steady(team)
        half = W(team, hp=0, bp=10, comp=10, longs=1)  # no high pressing, 100% completion
        return W(team, hp=30, bp=100, comp=70, longs=12), half, half

    d = run_ticks(pressing_down, range(31, 36))
    assert d.findings and d.findings[0].direction is Direction.DECREASE


# -- integration on simulated matches ----------------------------------------------------

@cache
def pair(seed):
    treated = simulate_match(seed)
    control = simulate_match(seed, control_script(treated.ground_truth.script))
    return treated, control


@cache
def run(seed, which):
    r = pair(seed)[which]
    return detect(r.setup, r.events)


@pytest.mark.parametrize("seed", [0, 42])
def test_findings_are_well_formed_and_use_only_released_past_events(seed):
    for which in (0, 1):
        r, result = pair(seed)[which], run(seed, which)
        by_id = {e.event_id: (i, e) for i, e in enumerate(r.events)}
        releases = release_times(r.events)
        for f in result.findings:
            detected = MatchTime(f.detected_period, f.detected_clock_ms)
            assert f.supporting_event_ids
            for eid in f.supporting_event_ids:
                i, e = by_id[eid]
                assert e.team_id == f.team_id and e.event_type in ("pressure", "possession_change")
                assert releases[i] is not None and releases[i] <= detected
            assert not re.search(r"\b(forced|because|due to|led to|resulted in)\b", f.statement.lower())
            assert "does not establish" in f.statement


@pytest.mark.parametrize("seed", [0, 42])
@pytest.mark.parametrize("cutoff", [MatchTime(1, 40 * 60_000), MatchTime(2, 15 * 60_000),
                                    MatchTime(2, 33 * 60_000)])
def test_analysis_to_cutoff_equals_analysis_of_prefix(seed, cutoff):
    r, control = pair(seed)
    full = detect(r.setup, r.events, until=cutoff)
    started = [e for e in r.events if event_time(e) <= cutoff]
    assert detect(r.setup, started, until=cutoff) == full
    # Replacing everything after the cutoff with a different future changes nothing before it.
    other_future = [e for e in control.events if event_time(e) > cutoff]
    assert detect(r.setup, started + other_future, until=cutoff) == full
    # A fresh detector given exactly the events visible at the cutoff computes the same metrics.
    # (Status can differ: persistence legitimately depends on earlier ticks.)
    fresh = PressingChangeDetector(r.setup)
    fresh.ingest(AsOfFeed(r.events).visible(cutoff))
    fresh.evaluate(cutoff)
    last = {a.team_id: a.metrics for a in full.assessments[-2:]}
    assert full.assessments[-1].period == cutoff.period
    assert {a.team_id: a.metrics for a in fresh.assessments} == last


@pytest.mark.parametrize("seed", [0, 42])
def test_hidden_script_cannot_influence_results_before_it_shows_in_events(seed):
    treated, control = pair(seed)
    cut = treated.ground_truth.applied[0].first_event_sequence
    before = event_time(treated.events[cut - 1])
    assert detect(treated.setup, treated.events, until=before) == \
        detect(control.setup, control.events, until=before)


def test_detection_is_deterministic_and_serializable():
    r = pair(42)[0]
    result = detect(r.setup, r.events)
    assert result == detect(r.setup, list(r.events)) == run(42, 0)
    assert DetectionResult.model_validate_json(result.model_dump_json()) == result
