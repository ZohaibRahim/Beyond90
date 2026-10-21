"""Benchmark harness tests. They never run the development or held-out seeds."""

import pytest

from beyond90.benchmark import DEV_SEEDS, HOLDOUT_SEEDS, HoldoutLockedError, seeds_for
from beyond90.benchmark.scoring import (
    CANDIDATES,
    CONSERVATIVE_ORDER,
    ConfigSummary,
    PairScore,
    score_pair,
    select,
    simulate_pair,
    switch_elapsed_ms,
    wilson,
)
from beyond90.benchmark.splits import _draw
from beyond90.detection import DEFAULT_CONFIG

MIN = 60_000


def test_split_is_frozen_disjoint_and_excludes_inspected_seeds():
    assert (list(DEV_SEEDS), list(HOLDOUT_SEEDS)) == _draw()
    assert len(set(DEV_SEEDS)) == len(set(HOLDOUT_SEEDS)) == 30
    assert not set(DEV_SEEDS) & set(HOLDOUT_SEEDS)
    assert not ({42} | set(range(30))) & (set(DEV_SEEDS) | set(HOLDOUT_SEEDS))


def test_holdout_is_locked_by_default():
    assert seeds_for("dev") == DEV_SEEDS
    with pytest.raises(HoldoutLockedError):
        seeds_for("holdout")
    with pytest.raises(ValueError):
        seeds_for("test")


def test_candidates_vary_only_minimum_data_thresholds():
    assert CANDIDATES["original"] == DEFAULT_CONFIG
    assert set(CONSERVATIVE_ORDER) == set(CANDIDATES)
    data_fields = {"min_baseline_ms", "min_baseline_buildup", "min_recent_buildup", "min_half_buildup"}
    for cfg in CANDIDATES.values():
        for name, value in vars(cfg).items():
            if name not in data_fields:
                assert value == getattr(DEFAULT_CONFIG, name), name


def test_wilson_interval():
    lo, hi = wilson(15, 30)
    assert lo < 0.5 < hi and wilson(0, 30)[0] == 0.0 and wilson(30, 30)[1] == 1.0


def test_score_pair_on_seed_42_matches_stage_3a_run():
    s = score_pair(42, DEFAULT_CONFIG)
    treated, _ = simulate_pair(42)
    assert s.switch_ms == switch_elapsed_ms(treated)
    assert s.outcome == "correct" and s.control_false_alarms == 0 and s.treated_false_alarms == 0
    assert s.delay_ms == pytest.approx(14.4 * MIN, abs=0.1 * MIN)  # reported in Stage 3A
    assert 0 < s.target_post_insufficient <= s.target_post_ticks
    assert s.ie_reasons and s.opportunity_per_10min > 0


def _summary(name, outcomes, delays_min=(), control_fa=0, early=0):
    scores, it = [], iter(delays_min)
    for o in outcomes:
        delay = next(it) if o == "correct" else 0
        scores.append(PairScore(seed=0, switch_ms=60 * MIN, outcome=o,
                                detected_ms=None if o == "miss" else 60 * MIN + delay * MIN * (1 if o == "correct" else -1),
                                treated_false_alarms=0, control_false_alarms=0, team_ticks=1, insufficient_ticks=0,
                                target_post_ticks=1, target_post_insufficient=0))
    for i in range(control_fa):
        scores[i].control_false_alarms += 1
    return ConfigSummary(name, CANDIDATES[name], scores)


def test_selection_rule():
    base = ["correct"] * 10 + ["miss"] * 20
    a = _summary("original", base, [14] * 10)
    # One extra detection is not enough; two are.
    b = _summary("recent12", ["correct"] * 11 + ["miss"] * 19, [14] * 11)
    assert select([a, b]) == "original"
    c = _summary("recent10", ["correct"] * 12 + ["miss"] * 18, [14] * 12)
    assert select([a, b, c]) == "recent10"
    # Same recall but >= 2 min faster wins; 1 min faster does not.
    assert select([a, _summary("recent12", base, [12] * 10)]) == "recent12"
    assert select([a, _summary("recent12", base, [13] * 10)]) == "original"
    # Too many control false alarms makes a config ineligible, however good its recall.
    noisy = _summary("recent8", ["correct"] * 30, [5] * 30, control_fa=4)
    assert not noisy.eligible and select([a, noisy]) == "original"
    assert select([_summary("original", base, [14] * 10, control_fa=4)]) is None
    # Early detections: at most one allowed.
    early = _summary("recent12", ["correct"] * 20 + ["early"] * 2 + ["miss"] * 8, [10] * 20)
    assert not early.eligible
