import statistics
from functools import cache

import pytest

from beyond90.analytics.possession import possession_intervals, possession_sequences, summarize_possession
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
    assert summary.in_play_ms == {"nbh": 4000, "kes": 1000 + 2000 + (2_730_000 - 20_000)}
    assert summary.contested_ms == 1000  # incomplete pass until the turnover is resolved
    assert summary.dead_ms == 11_000     # ball out until the throw-in
    assert summary.share("nbh") == pytest.approx(4000 / (4000 + summary.in_play_ms["kes"]))


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
    assert summary.ball_in_play_ms + summary.dead_ms == elapsed
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
