"""Markdown rendering of a detection run (public: built only from public data and detector output)."""

from __future__ import annotations

from beyond90.detection.detector import DetectionResult, EvidenceStatus
from beyond90.schemas import MatchSetup

STATUS_CHAR = {
    EvidenceStatus.INSUFFICIENT_EVIDENCE: "?",
    EvidenceStatus.NO_CHANGE: ".",
    EvidenceStatus.CANDIDATE: "c",
    EvidenceStatus.SUSTAINED_CHANGE: "S",
}


def _minute(period: int, clock_ms: int) -> str:
    base = 0 if period == 1 else 45
    return f"{base + clock_ms // 60_000}'"


def _v(value) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def render_detection_report(setup: MatchSetup, result: DetectionResult, label: str = "") -> str:
    short = {t.team_id: t.short_name for t in setup.teams}
    out = [f"# Pressing-change detection{f' — {label}' if label else ''}", "",
           f"Match `{result.match_id}`: {setup.home.name} vs {setup.away.name}. Evaluated every minute using only "
           "events fully observable at that minute (public data only).", "",
           "Findings describe associations between observed event rates. They do not explain why play changed "
           "and do not attribute any individual pass, turnover or goal to a tactical change.", "",
           "## Findings", ""]
    if not result.findings:
        out.append("No sustained pressing change detected.")
    for f in result.findings:
        out += [f"### {short[f.team_id]}: {f.direction} detected at {_minute(f.detected_period, f.detected_clock_ms)}"
                f" (period {f.detected_period}, {f.detected_clock_ms / 1000:.0f}s)", "",
                f.statement, "",
                f"- Status: {f.status}",
                f"- Primary z = {_v(f.metrics.get('primary_z'))}, rate ratio = {_v(f.metrics.get('rate_ratio'))}, "
                f"5-minute halves = {_v(f.metrics.get('half1_rate'))} / {_v(f.metrics.get('half2_rate'))}",
                f"- Support z: high regains {_v(f.metrics.get('high_regains_z'))}, opp defensive-third completion "
                f"{_v(f.metrics.get('opp_defensive_third_completion_z'))}, opp long-pass share "
                f"{_v(f.metrics.get('opp_long_pass_share_z'))}",
                f"- Supporting public event ids ({len(f.supporting_event_ids)}): "
                + ", ".join(f"`{i}`" for i in f.supporting_event_ids), ""]

    out += ["## Status timeline", "",
            "One character per minute: `?` insufficient evidence, `.` no change, `c` candidate, "
            "`S` sustained change.", "", "```"]
    for team in setup.team_ids:
        for period in (1, 2):
            marks = "".join(STATUS_CHAR[a.status] + ("" if a.direction is None else "")
                            for a in result.assessments if a.team_id == team and a.period == period)
            out.append(f"{short[team]} P{period}: {marks}")
    out += ["```", "", "## Candidate and sustained ticks", "",
            "| Minute | Team | Status | Direction | Primary z | Ratio | Reason |", "|---|---|---|---|---:|---:|---|"]
    for a in result.assessments:
        if a.status in (EvidenceStatus.CANDIDATE, EvidenceStatus.SUSTAINED_CHANGE):
            out.append(f"| {_minute(a.period, a.clock_ms)} | {short[a.team_id]} | {a.status} | {a.direction} | "
                       f"{_v(a.metrics.get('primary_z'))} | {_v(a.metrics.get('rate_ratio'))} | {a.reason} |")

    out += ["", "## Rolling metrics every 5 minutes (last 10 minutes)", "",
            "| Minute | Team | High pressures | Opp build-up passes | High press / build-up pass | High regains "
            "| Opp def-third completion | Opp long share | Opp keeper long share | High press / opp controlled min |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in result.assessments:
        if a.clock_ms % (5 * 60_000) == 0:
            m = a.metrics
            out.append(f"| {_minute(a.period, a.clock_ms)} | {short[a.team_id]} | {m['recent_high_pressures']} | "
                       f"{m['recent_opp_buildup_passes']} | {_v(m['recent_high_pressures_per_buildup_pass'])} | "
                       f"{m['recent_high_regains']} | {_v(m['recent_opp_defensive_third_completion'])} | "
                       f"{_v(m['recent_opp_long_pass_share'])} | {_v(m['recent_opp_keeper_long_share'])} | "
                       f"{_v(m['recent_high_pressures_per_opp_controlled_min'])} |")
    out.append("")
    return "\n".join(out)
