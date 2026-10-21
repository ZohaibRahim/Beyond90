"""Public, human-readable Markdown match report.

Built ONLY from the public match setup and event stream, so it is safe to show
anywhere the live system's outputs are shown. It contains no hidden tactical
information.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from beyond90.analytics.box_score import WINDOW_LABELS, TeamStats, compute_team_stats, window_index
from beyond90.analytics.possession import (
    PossessionSequence,
    PossessionSummary,
    possession_intervals,
    possession_sequences,
    summarize_possession,
)
from beyond90.schemas import (
    MatchEvent,
    MatchSetup,
    PassEvent,
    PeriodEndEvent,
    Position,
    ShotEvent,
    ShotOutcome,
    SubstitutionEvent,
    TeamSheet,
)

UNSUPPORTED_MECHANICS = (
    "Penalties, cards (and sendings-off), injuries, own goals, drop balls, advantage play, extra time "
    "and shoot-outs are not simulated.",
    "Fouls never occur inside the penalty area (so no penalties arise).",
    "No off-ball player positions, formations in motion or dribble/carry events. Carries are implicit: "
    "the next action may start a few metres from where the previous pass ended.",
    "Goalkeepers only act near their own goal: they receive deliberate back passes, take goal kicks, "
    "hold saves and claim loose balls; they never join attacks.",
    "Substitutions occur only in the second half (including at half-time) and like-for-like where possible.",
    "Shot quality is an internal function of distance and body part; it is not emitted in events.",
)


def match_minute(event: MatchEvent) -> str:
    base, minute = (0, 45) if event.period == 1 else (45, 90)
    played = base + event.clock_ms // 60_000 + 1
    return f"{minute}+{played - minute}'" if played > minute else f"{played}'"


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.1f}%"


def _mmss(ms: int) -> str:
    return f"{ms // 60_000}:{ms // 1000 % 60:02d}"


def apportion(values: Sequence[int], total_units: int) -> list[int]:
    """Largest-remainder rounding: integer parts proportional to ``values`` that sum to ``total_units``.

    Used only for display, so rounded rows add up to the rounded total.
    """
    whole = sum(values)
    if whole == 0:
        return [0] * len(values)
    exact = [v * total_units / whole for v in values]
    parts = [int(x) for x in exact]
    by_remainder = sorted(range(len(values)), key=lambda i: (-(exact[i] - parts[i]), i))
    for i in by_remainder[: total_units - sum(parts)]:
        parts[i] += 1
    return parts


def shape_from_positions(team: TeamSheet) -> str:
    counts = Counter(team.player(p).position for p in team.starting_xi)
    return f"{counts[Position.DEFENDER]}-{counts[Position.MIDFIELDER]}-{counts[Position.FORWARD]}"


def _stat_rows(setup: MatchSetup, stats: dict[str, TeamStats], poss: PossessionSummary) -> list[str]:
    home, away = (stats[t] for t in setup.team_ids)
    rows = [f"| Stat | {setup.home.name} | {setup.away.name} |", "|---|---:|---:|"]
    hid, aid = setup.team_ids
    rows.append(f"| possession (time-based estimate) | {_pct(poss.share(hid))} | {_pct(poss.share(aid))} |")
    for key, h in home.as_dict().items():
        rows.append(f"| {key.replace('_', ' ')} | {h} | {away.as_dict()[key]} |")
    rows.append(f"| pass completion | {_pct(home.pass_completion)} | {_pct(away.pass_completion)} |")
    total = home.passes + away.passes
    if total:
        rows.append(f"| pass share (not possession) | {_pct(home.passes / total)} | {_pct(away.passes / total)} |")
    return rows


class _Describer:
    def __init__(self, setup: MatchSetup) -> None:
        self.names = {p.player_id: p.name for t in setup.teams for p in t.squad}
        self.short = {t.team_id: t.short_name for t in setup.teams}

    def __call__(self, e: MatchEvent) -> str:
        names = self.names
        head = f"{e.sequence:5d} {match_minute(e):>7} P{e.period} {e.clock_ms / 1000:7.1f}s {e.event_type:<17}"
        team = self.short.get(getattr(e, "team_id", ""), "")
        detail = names[e.player_id] if getattr(e, "player_id", None) else ""
        if isinstance(e, PassEvent):
            to = f" -> {names[e.recipient_id]}" if e.recipient_id else ""
            detail += (f"{to} [{e.outcome}] ({e.location.x:.1f},{e.location.y:.1f})"
                       f"->({e.end_location.x:.1f},{e.end_location.y:.1f})")
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


def _sequence_line(setup: MatchSetup, seq: PossessionSequence, short: dict[str, str]) -> str:
    first, last = seq.events[0], seq.events[-1]
    return (f"{short[seq.team_id]} {match_minute(first)}–{match_minute(last)}: {seq.passes} passes, "
            f"{seq.duration_ms / 1000:.0f}s, events {first.sequence}–{last.sequence}, ended: {seq.end_reason}")


def render_match_report(setup: MatchSetup, events: Sequence[MatchEvent], event_sample: int = 30) -> str:
    describe = _Describer(setup)
    names, short = describe.names, describe.short
    home, away = setup.team_ids
    full = compute_team_stats(setup, events)
    halftime_idx = next(i for i, e in enumerate(events) if isinstance(e, PeriodEndEvent))
    ht = compute_team_stats(setup, events[: halftime_idx + 1])
    intervals = possession_intervals(setup, events)
    poss = summarize_possession(setup, intervals)
    sequences = possession_sequences(setup, events)

    out: list[str] = [
        f"# Match report: {setup.home.name} {full[home].goals}-{full[away].goals} {setup.away.name}",
        "",
        "Public report: built only from the public match setup and event stream.",
        "",
        f"- Match id: `{setup.match_id}`",
        f"- Half-time: {ht[home].goals}-{ht[away].goals}",
        f"- Total public events: {len(events)}",
    ]
    for e in events:
        if isinstance(e, PeriodEndEvent):
            out.append(f"- Period {e.period} length: {_mmss(e.clock_ms)}")
    out += [
        f"- Ends: {short[setup.first_half_x105_team_id]} attacked toward x=105 in the first half "
        f"(ends swap at half-time); {short[setup.first_half_kickoff_team_id]} kicked off.",
        "",
        "## Time accounting",
        "",
        "Every interval between consecutive events belongs to exactly one category, so the rows sum to the "
        "elapsed match time.",
        "",
        "| Category | Time | Share of elapsed |",
        "|---|---:|---:|",
    ]
    elapsed = poss.elapsed_ms
    rows = [(f"Controlled by {setup.team(t).name}", poss.controlled_ms[t]) for t in setup.team_ids]
    rows += [("Contested in play (incomplete pass in flight, loose ball, turnover not yet completed)",
              poss.contested_ms),
             ("Stoppages (ball out of play, fouls, offsides, goals, substitutions)", poss.stoppage_ms)]
    total_s = round(elapsed / 1000)
    secs = apportion([ms for _, ms in rows], total_s)
    tenths = apportion([ms for _, ms in rows], 1000)
    out += [f"| {label} | {_mmss(sec * 1000)} | {t / 10:.1f}% |" for (label, _), sec, t in zip(rows, secs, tenths)]
    out += [f"| **Elapsed match time** | **{_mmss(total_s * 1000)}** | 100.0% |",
            "",
            f"Ball in play = controlled + contested = {_mmss(sum(secs[:3]) * 1000)}. Rows are rounded to the "
            "second so that they add up to the total shown.",
            "",
            "Possession is a time-based estimate: each team's share of *controlled* time. Contested time and "
            "stoppages are excluded. A completed pass in flight counts for the passer. When a loose ball is "
            "followed by a restart, the moment it left play is not observed, so that whole interval counts as "
            "a stoppage. Pass share is shown separately and is not a possession measure.",
    ]

    out += ["", "## Line-ups and shape", ""]
    for team in setup.teams:
        def fmt(p: str, t: TeamSheet = team) -> str:
            pl = t.player(p)
            return f"{pl.shirt_number} {pl.name} ({pl.position})"
        out += [f"**{team.name}** — shape from listed positions: {shape_from_positions(team)}", "",
                f"XI: {', '.join(fmt(p) for p in team.starting_xi)}", "",
                f"Bench: {', '.join(fmt(p) for p in team.bench)}", ""]

    out += ["## Goals", ""]
    goals = [e for e in events if isinstance(e, ShotEvent) and e.outcome is ShotOutcome.GOAL]
    for g in goals:
        loc = setup.to_attacking_frame(g.location, g.team_id, g.period)
        dist = ((105 - loc.x) ** 2 + (34 - loc.y) ** 2) ** 0.5
        out.append(f"- {match_minute(g)} {short[g.team_id]} — {names[g.player_id]} "
                   f"({g.body_part.replace('_', ' ')}, {dist:.0f} m from goal centre) `{g.event_id}`")
    if not goals:
        out.append("- None")

    out += ["", "## Substitutions", ""]
    for s in (e for e in events if isinstance(e, SubstitutionEvent)):
        out.append(f"- {match_minute(s)} {short[s.team_id]}: {names[s.player_on_id]} on for {names[s.player_off_id]}")

    out += ["", "## Team statistics (full match)", "", *_stat_rows(setup, full, poss), ""]
    for period in (1, 2):
        keep = lambda e, p=period: e.period == p  # noqa: E731
        out += [f"### Period {period}", "",
                *_stat_rows(setup, compute_team_stats(setup, events, keep),
                            summarize_possession(setup, intervals, keep)), ""]

    out += ["## 15-minute trends", "",
            "High pressures / high turnovers = pressures / possessions won in the team's attacking third "
            "(x >= 70 m in its own attacking frame).", "",
            "| Window | Team | Possession | Passes | Pass compl. | Pressures | High pressures "
            "| High turnovers won | Shots |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for w, label in enumerate(WINDOW_LABELS):
        keep = lambda e, w=w: window_index(e) == w  # noqa: E731
        ws = compute_team_stats(setup, events, keep)
        wp = summarize_possession(setup, intervals, keep)
        for tid in setup.team_ids:
            s = ws[tid]
            out.append(f"| {label} | {short[tid]} | {_pct(wp.share(tid))} | {s.passes} | {_pct(s.pass_completion)} "
                       f"| {s.pressures} | {s.pressures_attacking_third} | {s.turnovers_won_attacking_third} "
                       f"| {s.shots} |")

    out += ["", "## Possession sequences", "",
            "A sequence is an unbroken spell of one team's possession; restarts by the same team continue it.",
            "", "| Team | Sequences | Mean passes | Sequences with 10+ passes | Ended in shot/goal |",
            "|---|---:|---:|---:|---:|"]
    for tid in setup.team_ids:
        mine = [s for s in sequences if s.team_id == tid]
        shots = sum(s.end_reason.startswith(("shot", "goal")) for s in mine)
        mean = sum(s.passes for s in mine) / len(mine) if mine else 0
        out.append(f"| {short[tid]} | {len(mine)} | {mean:.1f} | {sum(s.passes >= 10 for s in mine)} | {shots} |")
    reasons = Counter(s.end_reason for s in sequences)
    out += ["", "How sequences ended: " + ", ".join(f"{k} {v}" for k, v in reasons.most_common()), ""]

    out += ["### Longest sequences per team", ""]
    for tid in setup.team_ids:
        for seq in sorted((s for s in sequences if s.team_id == tid), key=lambda s: -s.passes)[:2]:
            out += [f"**{_sequence_line(setup, seq, short)}**", "", "```", *map(describe, seq.events), "```", ""]

    out += ["## Build-up to goals", ""]
    for g in goals:
        seq = next(s for s in sequences if g in s.events)
        out += [f"### {match_minute(g)} {short[g.team_id]} goal — {_sequence_line(setup, seq, short)}", "",
                "```", *map(describe, seq.events), "```", ""]
    if not goals:
        out += ["No goals.", ""]

    counts = Counter(e.event_type for e in events)
    out += ["## Event type counts", "", "| Event type | Count |", "|---|---:|"]
    out += [f"| {k} | {v} |" for k, v in sorted(counts.items())]
    out += ["", f"## First {event_sample} events", "", "```", *map(describe, events[:event_sample]), "```", ""]

    out += ["## Unsupported match mechanics", ""]
    out += [f"- {line}" for line in UNSUPPORTED_MECHANICS]
    out.append("")
    return "\n".join(out)
