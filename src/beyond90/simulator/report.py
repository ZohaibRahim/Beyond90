"""Human-readable Markdown match report for manual realism review.

Statistics come from the public event stream via ``beyond90.analytics``. The
hidden ground truth is shown only in a clearly separated final section, because
this report is a developer artefact, not a live-system output.
"""

from __future__ import annotations

from collections import Counter

from beyond90.analytics.box_score import WINDOW_LABELS, TeamStats, compute_team_stats, window_index
from beyond90.schemas import (
    MatchEvent,
    PassEvent,
    PassOutcome,
    PeriodEndEvent,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
)
from beyond90.simulator.engine import SimulationResult


def match_minute(event: MatchEvent) -> str:
    base, minute = (0, 45) if event.period == 1 else (45, 90)
    played = base + event.clock_ms // 60_000 + 1
    return f"{minute}+{played - minute}'" if played > minute else f"{played}'"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.1f}%"


def _stat_rows(setup, stats: dict[str, TeamStats]) -> list[str]:
    home, away = (stats[t] for t in setup.team_ids)
    rows = [f"| Stat | {setup.home.name} | {setup.away.name} |", "|---|---:|---:|"]
    for key, h in home.as_dict().items():
        rows.append(f"| {key.replace('_', ' ')} | {h} | {away.as_dict()[key]} |")
    rows.append(f"| pass completion | {_pct(home.pass_completion)} | {_pct(away.pass_completion)} |")
    total = home.passes + away.passes
    if total:
        rows.append(f"| pass share (possession proxy) | {_pct(home.passes / total)} | {_pct(away.passes / total)} |")
    return rows


def render_report(result: SimulationResult, event_sample: int = 40) -> str:
    setup, events, gt = result.setup, result.events, result.ground_truth
    names = {p.player_id: p.name for t in setup.teams for p in t.squad}
    short = {t.team_id: t.short_name for t in setup.teams}
    full = compute_team_stats(setup, events)
    halftime_idx = next(i for i, e in enumerate(events) if isinstance(e, PeriodEndEvent))
    ht = compute_team_stats(setup, events[: halftime_idx + 1])
    home, away = setup.team_ids

    out: list[str] = [
        f"# Match report: {setup.home.name} {full[home].goals}-{full[away].goals} {setup.away.name}",
        "",
        f"- Match id: `{setup.match_id}`  ·  Simulation seed: {gt.script.simulation_seed}"
        f"  ·  Simulator {gt.simulator_version}",
        f"- Half-time: {ht[home].goals}-{ht[away].goals}",
        f"- Total public events: {len(events)}",
    ]
    for e in events:
        if isinstance(e, PeriodEndEvent):
            out.append(f"- Period {e.period} length: {e.clock_ms // 60_000}:{e.clock_ms // 1000 % 60:02d}")
    out.append(f"- Ends: {short[setup.first_half_x105_team_id]} attacked toward x=105 in the first half "
               f"(ends swap at half-time); {short[setup.first_half_kickoff_team_id]} kicked off.")

    out += ["", "## Line-ups", ""]
    for team in setup.teams:
        xi = ", ".join(f"{team.player(p).shirt_number} {names[p]} ({team.player(p).position})"
                       for p in team.starting_xi)
        bench = ", ".join(f"{team.player(p).shirt_number} {names[p]} ({team.player(p).position})"
                          for p in team.bench)
        out += [f"**{team.name}** XI: {xi}", "", f"Bench: {bench}", ""]

    out += ["## Goals", ""]
    goals = [e for e in events if isinstance(e, ShotEvent) and e.outcome is ShotOutcome.GOAL]
    for g in goals:
        prev = events[g.sequence - 1] if g.sequence else None
        assist = ""
        if isinstance(prev, PassEvent) and prev.outcome is PassOutcome.COMPLETE and prev.recipient_id == g.player_id:
            assist = f", assist {names[prev.player_id]}"
        loc = setup.to_attacking_frame(g.location, g.team_id, g.period)
        dist = ((105 - loc.x) ** 2 + (34 - loc.y) ** 2) ** 0.5
        out.append(f"- {match_minute(g)} {short[g.team_id]} — {names[g.player_id]} "
                   f"({g.body_part.replace('_', ' ')}, {dist:.0f} m{assist}) `{g.event_id}`")
    if not goals:
        out.append("- None")

    out += ["", "## Substitutions", ""]
    for s in (e for e in events if isinstance(e, SubstitutionEvent)):
        out.append(f"- {match_minute(s)} {short[s.team_id]}: {names[s.player_on_id]} on for {names[s.player_off_id]}")

    out += ["", "## Team statistics (full match)", "", *_stat_rows(setup, full), ""]
    for period in (1, 2):
        out += [f"### Period {period}", "",
                *_stat_rows(setup, compute_team_stats(setup, events, lambda e, p=period: e.period == p)), ""]

    out += ["## 15-minute windows", "",
            "High pressures / high turnovers = pressures / possessions won in the team's attacking third "
            "(x >= 70 m in its own attacking frame).", "",
            "| Window | Team | Pressures | High pressures | High turnovers won | Opp. pass completion |",
            "|---|---|---:|---:|---:|---:|"]
    for w, label in enumerate(WINDOW_LABELS):
        ws = compute_team_stats(setup, events, lambda e, w=w: window_index(e) == w)
        for tid in setup.team_ids:
            s, o = ws[tid], ws[setup.opponent_id(tid)]
            out.append(f"| {label} | {short[tid]} | {s.pressures} | {s.pressures_attacking_third} "
                       f"| {s.turnovers_won_attacking_third} | {_pct(o.pass_completion)} |")

    counts = Counter(e.event_type for e in events)
    out += ["", "## Event type counts", "", "| Event type | Count |", "|---|---:|"]
    out += [f"| {k} | {v} |" for k, v in sorted(counts.items())]

    out += ["", f"## First {event_sample} events", "", "```"]
    for e in events[:event_sample]:
        out.append(_describe(e, names, short))
    out += ["```", ""]
    for g in goals:
        out += [f"### Build-up to {match_minute(g)} goal", "", "```"]
        out += [_describe(e, names, short) for e in events[max(0, g.sequence - 10): g.sequence + 1]]
        out += ["```", ""]

    out += ["---", "", "## HIDDEN ground truth (simulator only — never available to the live system)", ""]
    for b in gt.script.baselines:
        out.append(f"- Baseline pressing, {short[b.team_id]}: {b.pressing}")
    applied = {a.intervention_id: a for a in gt.applied}
    for iv in gt.script.interventions:
        a = applied.get(iv.intervention_id)
        minute = (0 if iv.effective_period == 1 else 45) + iv.effective_clock_ms / 60_000
        where = f"first affected event `{a.first_event_id}` (sequence {a.first_event_sequence})" if a else "never applied"
        out.append(f"- `{iv.intervention_id}` {iv.intervention_type} for {short[iv.team_id]} from "
                   f"{minute:.1f}' -> {getattr(iv, 'intensity', '')}; {where}. {iv.note or ''}")
    out += ["", "## Model simplifications", "",
            "- One ball carrier at a time; no off-ball player positions. Carries are implicit "
            "(the next action may start a few metres from the previous pass end).",
            "- No penalties, cards, injuries, own goals or extra time. Fouls never occur inside the penalty area.",
            "- Shot quality is an internal function of distance (hidden, never emitted).",
            ""]
    return "\n".join(out)


def _describe(e: MatchEvent, names: dict[str, str], short: dict[str, str]) -> str:
    head = f"{e.sequence:5d} {match_minute(e):>7} P{e.period} {e.clock_ms / 1000:7.1f}s {e.event_type:<17}"
    team = short.get(getattr(e, "team_id", ""), "")
    detail = ""
    if hasattr(e, "player_id") and getattr(e, "player_id", None):
        detail += names[e.player_id]
    if isinstance(e, PassEvent):
        to = f" -> {names[e.recipient_id]}" if e.recipient_id else ""
        detail += f"{to} [{e.outcome}] ({e.location.x:.1f},{e.location.y:.1f})->({e.end_location.x:.1f},{e.end_location.y:.1f})"
    elif isinstance(e, ShotEvent):
        detail += f" [{e.outcome}, {e.body_part}] ({e.location.x:.1f},{e.location.y:.1f})"
    elif isinstance(e, SubstitutionEvent):
        detail = f"{names[e.player_on_id]} for {names[e.player_off_id]}"
    else:
        for attr in ("restart_type", "outcome", "cause"):
            if hasattr(e, attr):
                detail += f" [{getattr(e, attr)}]"
        if hasattr(e, "opponent_player_id"):
            detail += f" on {names[e.opponent_player_id]}"
        if hasattr(e, "location"):
            detail += f" ({e.location.x:.1f},{e.location.y:.1f})"
    return f"{head} {team:<4} {detail}".rstrip()
