import statistics
from functools import cache

import pytest

from beyond90.analytics.box_score import compute_team_stats
from beyond90.ground_truth import GroundTruthRecord
from beyond90.schemas import (
    EventAdapter,
    MatchSetup,
    MatchValidationError,
    PossessionChangeCause,
    PossessionChangeEvent,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
    validate_event_sequence,
    validate_match,
)
from beyond90.simulator import control_script, simulate_match, write_outputs

SEEDS = list(range(10))


@cache
def sim(seed: int):
    return simulate_match(seed)


@cache
def control(seed: int):
    return simulate_match(seed, control_script(sim(seed).ground_truth.script))


@pytest.mark.parametrize("seed", SEEDS)
def test_simulated_match_passes_full_validation(seed):
    r = sim(seed)
    validate_match(r.setup, r.events)


@pytest.mark.parametrize("seed", SEEDS)
def test_score_reconciles(seed):
    r = sim(seed)
    goals = {tid: 0 for tid in r.setup.team_ids}
    for e in r.events:
        if isinstance(e, ShotEvent) and e.outcome is ShotOutcome.GOAL:
            goals[e.team_id] += 1
    stats = compute_team_stats(r.setup, r.events)
    assert goals == r.ground_truth.final_score == validate_match(r.setup, r.events).score
    assert {tid: s.goals for tid, s in stats.items()} == goals


@pytest.mark.parametrize("seed", SEEDS)
def test_chronological_and_contiguous(seed):
    events = sim(seed).events
    validate_event_sequence(events)
    assert [e.sequence for e in events] == list(range(len(events)))
    assert [e.event_type for e in events].count("period_end") == 2


def test_same_seed_is_reproducible():
    a, b = simulate_match(7), simulate_match(7)
    assert [e.model_dump_json() for e in a.events] == [e.model_dump_json() for e in b.events]
    assert a.ground_truth == b.ground_truth


def test_different_seeds_differ():
    assert sim(0).events != sim(1).events
    assert sim(0).setup.match_id != sim(1).setup.match_id


@pytest.mark.parametrize("seed", SEEDS)
def test_player_eligibility(seed):
    r = sim(seed)
    for e in r.events:
        for attr in ("player_id", "recipient_id", "player_off_id", "player_on_id"):
            pid = getattr(e, attr, None)
            if pid is not None:
                assert r.setup.team_of_player(pid) == e.team_id, (e.event_id, attr)
        if hasattr(e, "opponent_player_id"):
            assert r.setup.team_of_player(e.opponent_player_id) == r.setup.opponent_id(e.team_id)


@pytest.mark.parametrize("seed", SEEDS)
def test_substitutions(seed):
    r = sim(seed)
    subs = [e for e in r.events if isinstance(e, SubstitutionEvent)]
    for tid in r.setup.team_ids:
        mine = [s for s in subs if s.team_id == tid]
        assert 1 <= len(mine) <= r.setup.max_substitutions
        assert len({s.player_on_id for s in mine}) == len(mine)
        assert not {s.player_on_id for s in mine} & {s.player_off_id for s in mine}  # nobody re-enters
    assert all(s.period == 2 for s in subs)


@pytest.mark.parametrize("seed", SEEDS)
def test_pitch_orientation_flips_at_halftime(seed):
    r = sim(seed)
    for e in r.events:
        if isinstance(e, ShotEvent):
            toward_105 = r.setup.attacks_toward_x105(e.team_id, e.period)
            assert (e.location.x > 52.5) == toward_105, e.event_id


@pytest.mark.parametrize("seed", SEEDS)
def test_keeper_holds_saves(seed):
    r = sim(seed)
    keepers = {p.player_id for t in r.setup.teams for p in t.squad if p.position == "GK"}
    for e in r.events:
        if isinstance(e, PossessionChangeEvent) and e.cause is PossessionChangeCause.SHOT:
            shot = r.events[int(e.related_event_id.rsplit("-", 1)[1])]
            assert isinstance(shot, ShotEvent)
            if shot.outcome is ShotOutcome.SAVED:
                assert e.player_id in keepers


def test_tampered_stream_breaks_possession_consistency():
    r = sim(0)
    i = next(i for i, e in enumerate(r.events) if isinstance(e, PossessionChangeEvent))
    with pytest.raises(MatchValidationError):
        validate_match(r.setup, r.events[:i] + r.events[i + 1:])


def test_plausible_match_statistics():
    """Loose sanity bounds averaged over seeds; realism itself is judged by manual review."""
    per_team = [s for seed in SEEDS for s in compute_team_stats(sim(seed).setup, sim(seed).events).values()]
    mean = lambda key: statistics.mean(getattr(s, key) for s in per_team)  # noqa: E731
    assert 350 <= mean("passes") <= 750
    assert 0.70 <= statistics.mean(s.pass_completion for s in per_team) <= 0.88
    assert 7 <= mean("shots") <= 18
    assert 0.7 <= mean("goals") <= 2.0
    assert 2 <= mean("corners") <= 9
    assert 5 <= mean("fouls") <= 16
    for seed in SEEDS:
        for e in sim(seed).events:
            if e.event_type == "period_end":
                assert 45 * 60_000 <= e.clock_ms <= 52 * 60_000


# -- hidden intervention behaviour --------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
def test_intervention_applied_at_scripted_time(seed):
    r = sim(seed)
    (iv,) = r.ground_truth.script.interventions
    (applied,) = r.ground_truth.applied
    first = r.events[applied.first_event_sequence]
    assert first.event_id == applied.first_event_id
    assert (first.period, first.clock_ms) >= (iv.effective_period, iv.effective_clock_ms)
    before = r.events[applied.first_event_sequence - 1]
    assert (before.period, before.clock_ms) < (iv.effective_period, iv.effective_clock_ms)


@pytest.mark.parametrize("seed", SEEDS)
def test_events_identical_to_control_until_intervention(seed):
    r, c = sim(seed), control(seed)
    cut = r.ground_truth.applied[0].first_event_sequence
    assert r.events[:cut] == c.events[:cut]
    assert r.events != c.events
    assert c.ground_truth.applied == ()


def test_pressing_team_responds_probabilistically():
    """Post-intervention high pressing rises vs the paired control, without any event labels."""
    def high_press_rate(result, cut):
        team = result.setup.away.team_id
        after = [e for e in result.events if e.sequence >= cut]
        minutes = (after[-1].clock_ms - after[0].clock_ms) / 60_000
        stats = compute_team_stats(result.setup, after)
        return stats[team].pressures_attacking_third / minutes

    treated, controlled = [], []
    for seed in SEEDS:
        cut = sim(seed).ground_truth.applied[0].first_event_sequence
        treated.append(high_press_rate(sim(seed), cut))
        controlled.append(high_press_rate(control(seed), cut))
    assert statistics.mean(treated) > 2 * statistics.mean(controlled)
    # Probabilistic, not deterministic: rates vary between matches.
    assert len({round(x, 3) for x in treated}) > 1


def test_unsupported_intervention_types_rejected():
    from beyond90.ground_truth import TempoChange

    script = sim(0).ground_truth.script
    tempo = TempoChange(intervention_id="iv-t", match_id=script.match_id, team_id="kes",
                        effective_period=2, effective_clock_ms=0, tempo="fast")
    with pytest.raises(NotImplementedError):
        simulate_match(0, script.model_copy(update={"interventions": (tempo,)}))


# -- outputs ----------------------------------------------------------------------

def test_outputs_split_public_and_private(tmp_path):
    r = sim(3)
    paths = write_outputs(r, tmp_path)
    public = paths["events"].parent
    assert sorted(p.name for p in public.iterdir()) == ["events.jsonl", "match_setup.json"]
    assert paths["ground_truth"].parent.name == "private" and paths["ground_truth"].parent != public

    setup = MatchSetup.model_validate_json(paths["setup"].read_text(encoding="utf-8"))
    events = [EventAdapter.validate_json(line) for line in paths["events"].read_text(encoding="utf-8").splitlines()]
    assert validate_match(setup, events).score == r.ground_truth.final_score
    assert GroundTruthRecord.model_validate_json(paths["ground_truth"].read_text(encoding="utf-8")) == r.ground_truth


def test_no_spatial_concentration_of_pass_receptions():
    """Regression: clamping once piled receptions on x=104 / x=1 / y=1 / y=67 and on the goal line."""
    from collections import Counter

    from beyond90.schemas import PassEvent, PassOutcome

    completed = deep = longest_run = 0
    xs, ys = Counter(), Counter()
    for seed in SEEDS:
        r = sim(seed)
        run = 0
        for e in r.events:
            if not (isinstance(e, PassEvent) and e.outcome is PassOutcome.COMPLETE):
                continue
            end = r.setup.to_attacking_frame(e.end_location, e.team_id, e.period)
            completed += 1
            xs[round(end.x)] += 1
            ys[round(end.y)] += 1
            if end.x >= 98:
                deep += 1
                run += 1
                longest_run = max(longest_run, run)
            else:
                run = 0
    assert deep / completed < 0.04
    assert longest_run <= 4
    # No single 1 m line across or along the pitch holds an outsized share of receptions.
    assert max(xs.values()) / completed < 0.03
    assert max(ys.values()) / completed < 0.04
