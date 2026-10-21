"""Goalkeeper involvement comes from deliberate back passes, kicks, saves and claims."""

import statistics
from functools import cache

import pytest

from beyond90.schemas import PassEvent, PassOutcome, Position
from beyond90.simulator import control_script, simulate_match

SEEDS = range(10)


@cache
def sim(seed, control=False):
    r = simulate_match(seed)
    return simulate_match(seed, control_script(r.ground_truth.script)) if control else r


def keepers(setup):
    return {p.player_id for t in setup.teams for p in t.squad if p.position is Position.GOALKEEPER}


@pytest.mark.parametrize("seed", SEEDS)
def test_keeper_receives_only_near_own_goal(seed):
    r = sim(seed)
    gks = keepers(r.setup)
    received = 0
    for e in r.events:
        if isinstance(e, PassEvent) and e.recipient_id in gks:
            received += 1
            end = r.setup.to_attacking_frame(e.end_location, e.team_id, e.period)
            start = r.setup.to_attacking_frame(e.location, e.team_id, e.period)
            assert end.x <= 12.5 and abs(end.y - 34) <= 30, e.event_id
            assert start.x <= 46, "back passes come from the passer's own half"
        if isinstance(e, PassEvent) and e.player_id in gks:
            assert r.setup.to_attacking_frame(e.location, e.team_id, e.period).x <= 30, e.event_id
    assert received > 0


def test_back_passes_to_keeper_rise_when_pressed_high():
    """Mechanism check (not a count target): the pressed team recycles via its keeper more."""
    def to_keeper(r, cut):
        pressed = r.setup.home.team_id
        gks = keepers(r.setup)
        return sum(isinstance(e, PassEvent) and e.team_id == pressed and e.recipient_id in gks
                   and e.outcome is PassOutcome.COMPLETE for e in r.events[cut:])

    treated, controlled = [], []
    for seed in SEEDS:
        cut = sim(seed).ground_truth.applied[0].first_event_sequence
        treated.append(to_keeper(sim(seed), cut))
        controlled.append(to_keeper(sim(seed, control=True), cut))
    assert statistics.mean(treated) > statistics.mean(controlled)
