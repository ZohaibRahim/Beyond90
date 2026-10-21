import statistics
from functools import cache

import pytest

from beyond90.analytics.possession import (
    TimeCategory,
    possession_intervals,
    possession_sequences,
    summarize_possession,
)
from beyond90.schemas import PeriodEndEvent, ShotEvent, ShotOutcome, SubstitutionEvent
from beyond90.simulator import simulate_match
from streams import SETUP, Stream


def mini_match():
    s = Stream()
    s.kickoff("kes", "kes-09", clock_ms=1000)
    s.pass_("kes", "kes-09", "kes-08", clock_ms=2000)
    s.pass_("kes", "kes-08", outcome="incomplete", clock_ms=4000)
    s.add("possession_change", team_id="nbh", previous_team_id="kes", cause="incomplete_pass",
          player_id="nbh-04", location={"x": 55, "y": 30}, clock_ms=5000)
    s.pass_("nbh", "nbh-04", outcome="out_of_play", end=(60, 68), clock_ms=9000)
    s.add("restart", team_id="kes", restart_type="throw_in", player_id="kes-03", location={"x": 60, "y": 68},
          clock_ms=20_000)
    s.end_period(1)  # 45:30
    return s.events


def test_time_based_possession_on_hand_built_stream():
    summary = summarize_possession(SETUP, possession_intervals(SETUP, mini_match()))
    assert summary.controlled_ms == {"nbh": 4000, "kes": 1000 + 2000 + (2_730_000 - 20_000)}
    assert summary.contested_ms == 1000  # incomplete pass until the turnover is resolved
    assert summary.stoppage_ms == 11_000  # ball out until the throw-in
    assert summary.elapsed_ms == 2_730_000 - 1000
    assert summary.share("nbh") == pytest.approx(4000 / (4000 + summary.controlled_ms["kes"]))


def _shot_then(follow):
    s = Stream()
    s.kickoff("kes", "kes-09", clock_ms=0)
    # kes attacks toward x=0 in period 1.
    s.add("shot", team_id="kes", player_id="kes-09", location={"x": 12, "y": 34}, outcome="saved",
          body_part="right_foot", clock_ms=10_000)
    follow(s)
    s.end_period(1)
    return summarize_possession(SETUP, possession_intervals(SETUP, s.events))


def test_loose_ball_followed_by_restart_is_a_stoppage():
    summary = _shot_then(lambda s: s.add("restart", team_id="kes", restart_type="corner_kick",
                                         player_id="kes-07", location={"x": 0, "y": 0}, clock_ms=40_000))
    assert summary.stoppage_ms == 30_000 and summary.contested_ms == 0


def test_loose_ball_recovered_in_play_is_contested():
    summary = _shot_then(lambda s: s.add("possession_change", team_id="nbh", previous_team_id="kes",
                                         cause="shot", player_id="nbh-01", location={"x": 2, "y": 34},
                                         clock_ms=12_000))
    assert summary.contested_ms == 2000 and summary.stoppage_ms == 0


def test_possession_sequences_on_hand_built_stream():
    seqs = possession_sequences(SETUP, mini_match())
    assert [(s.team_id, s.passes, s.end_reason) for s in seqs] == [
        ("kes", 2, "turnover (incomplete_pass)"),
        ("nbh", 1, "pass out_of_play"),
        ("kes", 0, "period end"),
    ]


@cache
def sim(seed):
    return simulate_match(seed)


@pytest.mark.parametrize("seed", range(5))
def test_possession_time_accounts_for_all_match_time(seed):
    r = sim(seed)
    summary = summarize_possession(r.setup, possession_intervals(r.setup, r.events))
    elapsed = 0
    for period in (1, 2):
        in_period = [e for e in r.events if e.period == period]
        elapsed += in_period[-1].clock_ms - in_period[0].clock_ms
    # Mutually exclusive categories reconcile exactly with elapsed match time.
    intervals = possession_intervals(r.setup, r.events)
    assert sum(iv.duration_ms for iv in intervals) == elapsed == summary.elapsed_ms
    assert sum(summary.controlled_ms.values()) + summary.contested_ms + summary.stoppage_ms == elapsed
    assert all((iv.team_id is not None) == (iv.category is TimeCategory.CONTROLLED) for iv in intervals)
    assert summary.share("nbh") + summary.share("kes") == pytest.approx(1.0)
    assert 45 * 60_000 <= summary.ball_in_play_ms <= 75 * 60_000


@pytest.mark.parametrize("seed", range(5))
def test_sequences_partition_the_match(seed):
    r = sim(seed)
    seqs = possession_sequences(r.setup, r.events)
    covered = [e.sequence for s in seqs for e in s.events]
    expected = [e.sequence for e in r.events if not isinstance(e, (SubstitutionEvent, PeriodEndEvent))]
    assert covered == expected  # every event exactly once, in order
    goals = sum(isinstance(e, ShotEvent) and e.outcome is ShotOutcome.GOAL for e in r.events)
    assert sum(s.end_reason == "goal" for s in seqs) == goals
    for s in seqs:
        for e in s.events:
            # On-ball actions in a sequence belong to the team in possession.
            if e.event_type in ("pass", "shot", "restart"):
                assert e.team_id == s.team_id
    assert 2 <= statistics.mean(s.passes for s in seqs) <= 7
