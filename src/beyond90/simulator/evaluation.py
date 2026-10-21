"""PRIVATE evaluation records (simulator side). Never shown to or read by the live system.

Compares each scripted match with its paired control (same seed and baselines,
no intervention) from the first affected event onward, to check that the
hidden script changes play plausibly, not just the number of pressure events.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from beyond90.analytics.box_score import compute_team_stats
from beyond90.analytics.possession import possession_intervals, possession_sequences, summarize_possession
from beyond90.schemas import PassEvent, PassOutcome, Position
from beyond90.simulator.engine import SimulationResult, simulate_match
from beyond90.simulator.scenario import control_script

PATTERN_NOT_CAUSE = (
    "These are aggregate pattern differences against a paired control. They do not show that the "
    "intervention caused any individual goal or chance: after the switch the two matches diverge "
    "entirely, so single events cannot be matched between them."
)

LONG_PASS_M = 30.0
KEEPER_LONG_M = 35.0

METRIC_LABELS = {
    "presser_pressures_pm": "Pressing team: pressures per min",
    "presser_high_pressures_pm": "Pressing team: attacking-third pressures per min",
    "presser_high_turnovers_pm": "Pressing team: attacking-third turnovers won per min",
    "presser_fouls_pm": "Pressing team: fouls per min",
    "presser_shots_pm": "Pressing team: shots per min",
    "pressed_possession": "Pressed team: possession share (time)",
    "pressed_pass_completion": "Pressed team: pass completion",
    "pressed_own_third_completion": "Pressed team: pass completion from own third",
    "pressed_long_share": f"Pressed team: share of passes >= {LONG_PASS_M:.0f} m",
    "pressed_passes_to_keeper_pm": "Pressed team: passes to own keeper per min",
    "pressed_keeper_long_share": f"Pressed team: keeper passes >= {KEEPER_LONG_M:.0f} m (share)",
    "pressed_passes_per_sequence": "Pressed team: passes per possession sequence",
    "pressed_shots_pm": "Pressed team: shots per min",
}


def post_cut_metrics(result: SimulationResult, pressing_team: str, cut: int) -> dict[str, float]:
    setup, events = result.setup, result.events
    pressed = setup.opponent_id(pressing_team)
    after = [e for e in events if e.sequence >= cut]
    minutes = sum(
        (max(e.clock_ms for e in after if e.period == p) - min(e.clock_ms for e in after if e.period == p)) / 60_000
        for p in {e.period for e in after}
    )
    stats = compute_team_stats(setup, after)
    s_press, s_pressed = stats[pressing_team], stats[pressed]
    poss = summarize_possession(setup, possession_intervals(setup, events), lambda e: e.sequence >= cut)
    keepers = {p.player_id for p in setup.team(pressed).squad if p.position is Position.GOALKEEPER}

    def frame_x(e, loc):
        return setup.to_attacking_frame(loc, e.team_id, e.period).x

    passes = [e for e in after if isinstance(e, PassEvent) and e.team_id == pressed]
    own_third = [e for e in passes if frame_x(e, e.location) < 35]
    length = lambda e: math.hypot(e.end_location.x - e.location.x, e.end_location.y - e.location.y)  # noqa: E731
    keeper_passes = [e for e in passes if e.player_id in keepers]
    seqs = [s for s in possession_sequences(setup, events) if s.team_id == pressed and s.events[0].sequence >= cut]

    def ratio(n: float, d: float) -> float:
        return n / d if d else float("nan")

    return {
        "presser_pressures_pm": s_press.pressures / minutes,
        "presser_high_pressures_pm": s_press.pressures_attacking_third / minutes,
        "presser_high_turnovers_pm": s_press.turnovers_won_attacking_third / minutes,
        "presser_fouls_pm": s_press.fouls / minutes,
        "presser_shots_pm": s_press.shots / minutes,
        "pressed_possession": poss.share(pressed) or float("nan"),
        "pressed_pass_completion": s_pressed.pass_completion or float("nan"),
        "pressed_own_third_completion": ratio(sum(e.outcome is PassOutcome.COMPLETE for e in own_third), len(own_third)),
        "pressed_long_share": ratio(sum(length(e) >= LONG_PASS_M for e in passes), len(passes)),
        "pressed_passes_to_keeper_pm": sum(e.recipient_id in keepers for e in passes) / minutes,
        "pressed_keeper_long_share": ratio(sum(length(e) >= KEEPER_LONG_M for e in keeper_passes), len(keeper_passes)),
        "pressed_passes_per_sequence": ratio(sum(s.passes for s in seqs), len(seqs)),
        "pressed_shots_pm": s_pressed.shots / minutes,
    }


def paired_metrics(seed: int) -> tuple[dict[str, float], dict[str, float]]:
    """(scripted, control) post-intervention metrics for one seed."""
    treated = simulate_match(seed)
    script = treated.ground_truth.script
    (iv,) = script.interventions
    (applied,) = treated.ground_truth.applied
    control = simulate_match(seed, control_script(script))
    cut = applied.first_event_sequence
    return post_cut_metrics(treated, iv.team_id, cut), post_cut_metrics(control, iv.team_id, cut)


def _fmt(v: float) -> str:
    return "-" if math.isnan(v) else f"{v:.3f}"


def intervention_review(seeds: Iterable[int]) -> str:
    seeds = list(seeds)
    pairs = [paired_metrics(s) for s in seeds]
    out = [
        "# PRIVATE — Pressing intervention review (paired controls)",
        "",
        f"Seeds: {seeds[0]}–{seeds[-1]} ({len(seeds)} matches). Each scripted match is compared with a control "
        "match (same seed and baselines, no intervention) from the first affected event onward. Before that "
        "point the two streams are identical. Values are per-match means.",
        "",
        PATTERN_NOT_CAUSE,
        "",
        "| Metric | Scripted | Control | Scripted / control | Seeds scripted > control |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in METRIC_LABELS.items():
        t = [p[0][key] for p in pairs if not math.isnan(p[0][key]) and not math.isnan(p[1][key])]
        c = [p[1][key] for p in pairs if not math.isnan(p[0][key]) and not math.isnan(p[1][key])]
        if not t:
            continue
        tm, cm = statistics.mean(t), statistics.mean(c)
        wins = sum(a > b for a, b in zip(t, c))
        out.append(f"| {label} | {_fmt(tm)} | {_fmt(cm)} | {_fmt(tm / cm) if cm else '-'} | {wins}/{len(t)} |")
    out.append("")
    return "\n".join(out)


def render_evaluation_record(result: SimulationResult) -> str:
    gt, setup = result.ground_truth, result.setup
    short = {t.team_id: t.short_name for t in setup.teams}
    out = ["# PRIVATE — Evaluation record (hidden ground truth)", "",
           "Never available to the live system. Pair with the public match report.", "",
           f"- Match id: `{setup.match_id}`  ·  seed {gt.script.simulation_seed}  ·  simulator {gt.simulator_version}",
           f"- Final score: " + ", ".join(f"{short[t]} {g}" for t, g in gt.final_score.items()), ""]
    for b in gt.script.baselines:
        out.append(f"- Baseline pressing, {short[b.team_id]}: {b.pressing}")
    applied = {a.intervention_id: a for a in gt.applied}
    for iv in gt.script.interventions:
        a = applied.get(iv.intervention_id)
        minute = (0 if iv.effective_period == 1 else 45) + iv.effective_clock_ms / 60_000
        where = f"first affected event `{a.first_event_id}` (sequence {a.first_event_sequence})" if a else "never applied"
        out.append(f"- `{iv.intervention_id}` {iv.intervention_type} for {short[iv.team_id]} from {minute:.1f}' "
                   f"-> {getattr(iv, 'intensity', '')}; {where}. {iv.note or ''}")
    if gt.applied:
        treated, control = paired_metrics(gt.script.simulation_seed)
        out += ["", "## This match vs its paired control (after the intervention)", "",
                PATTERN_NOT_CAUSE, "", "| Metric | Scripted | Control |", "|---|---:|---:|"]
        out += [f"| {METRIC_LABELS[k]} | {_fmt(treated[k])} | {_fmt(control[k])} |" for k in METRIC_LABELS]
    out.append("")
    return "\n".join(out)
