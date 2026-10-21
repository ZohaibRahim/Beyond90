"""Benchmark reports.

``render_summary`` contains aggregates only: no seed lists with switch times, and nothing
the live system could use. ``render_details`` lists per-match hidden switch times
and belongs in reports/private/.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from beyond90.benchmark.scoring import (
    CONSERVATIVE_ORDER,
    worsening,
    MAX_CONTROL_FA_PER_MATCH,
    MAX_EARLY,
    MINUTE_MS,
    ConfigSummary,
    opportunity_thirds,
    wilson,
)


def _f(v: float | None, digits: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


def _ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.0f}%, 95% CI {100 * lo:.0f}–{100 * hi:.0f}%)"


def render_summary(split: str, summaries: Sequence[ConfigSummary], proposal: str | None,
                   order: Sequence[str] = CONSERVATIVE_ORDER, title: str = "", notes: Sequence[str] = (),
                   selection_text: str = "Selection rule (protocol section 7)") -> str:
    n = summaries[0].n
    out = [f"# Detector benchmark — {split} split{f' — {title}' if title else ''}", "",
           *[line for note in notes for line in (note, "")],
           f"{n} seeds, each a treated match (hidden LOW→HIGH press switch for the away team in 53'–65') and its "
           "paired no-intervention control. Scoring and selection follow `docs/EVALUATION_PROTOCOL.md`, "
           "fixed before this run. All configurations are reported.", "",
           "z values are approximate heuristics (overlapping minute-by-minute windows are strongly dependent); "
           "the error rates below are the empirical measure.", "",
           "## Headline results", "",
           "| Config | Correct | Correct ≤15 min | Early | Missed | Median delay (min) | Mean | Min–max "
           "| Control false alarms | Controls with ≥1 FA | Treated non-target FA | Eligible |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|"]
    for s in summaries:
        d = s.delays_min
        out.append(
            f"| `{s.name}` | {_ci(s.correct, n)} | {s.correct_within} | {s.count('early')} | {s.count('miss')} | "
            f"{_f(s.median_delay_min)} | {_f(sum(d) / len(d) if d else None)} | "
            f"{_f(min(d) if d else None)}–{_f(max(d) if d else None)} | {s.control_fa} "
            f"({s.control_fa / n:.2f}/match) | {_ci(s.control_matches_with_fa, n)} | {s.treated_fa} | "
            f"{'yes' if s.eligible else 'no'} |")
    out += ["", f"Eligible = control false alarms ≤ {MAX_CONTROL_FA_PER_MATCH:.2f} per match and ≤ {MAX_EARLY} "
            "early detection.", "", "## Configurations", "",
            "| Config | min_baseline_ms | min_baseline_buildup | min_recent_buildup | min_half_buildup | z_primary |",
            "|---|---:|---:|---:|---:|---:|"]
    for s in summaries:
        c = s.config
        out.append(f"| `{s.name}` | {c.min_baseline_ms // MINUTE_MS} min | {c.min_baseline_buildup} | "
                   f"{c.min_recent_buildup} | {c.min_half_buildup} | {c.z_primary:.2f} |")
    out += ["", "All other thresholds as in Stage 3A (corroboration z 1.64, ratio 1.5, half ratio 1.2, "
            "3-tick persistence).", "", "## Insufficient evidence", "",
            "| Config | All team-ticks | Target team after switch | …baseline length | …baseline build-up "
            "| …recent build-up | …5-min half |", "|---|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        r = s.reason_pct()
        out.append(f"| `{s.name}` | {s.insufficient_pct:.1f}% | {s.target_post_insufficient_pct:.1f}% | "
                   f"{r['baseline_length']:.1f}% | {r['baseline_buildup']:.1f}% | {r['recent_buildup']:.1f}% | "
                   f"{r['half_buildup']:.1f}% |")
    out += ["", "Reason columns: share of target-team post-switch ticks naming that shortfall (a tick can "
            "name several).", ""]

    lo, hi = opportunity_thirds(summaries[0].scores)
    out += ["## Opportunity availability", "",
            "Opponent build-up passes per 10 minutes for the target team, switch to full time (public events). "
            f"Thirds of the {n} treated matches: low < {lo:.1f} ≤ middle < {hi:.1f} ≤ high.", "",
            "| Config | Low: correct | Low: median delay | Middle: correct | Middle: median delay "
            "| High: correct | High: median delay |", "|---|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        cells = []
        for band in ((None, lo), (lo, hi), (hi, None)):
            group = [p for p in s.scores if (band[0] is None or p.opportunity_per_10min >= band[0])
                     and (band[1] is None or p.opportunity_per_10min < band[1])]
            delays = sorted(p.delay_ms / MINUTE_MS for p in group if p.delay_ms is not None)
            med = delays[len(delays) // 2] if len(delays) % 2 else (
                (delays[len(delays) // 2 - 1] + delays[len(delays) // 2]) / 2 if delays else None)
            cells += [f"{sum(p.outcome == 'correct' for p in group)}/{len(group)}", _f(med)]
        out.append(f"| `{s.name}` | " + " | ".join(cells) + " |")

    out += ["", "## Proposed configuration", ""]
    if proposal is None:
        out.append("No configuration is eligible under the protocol; none is proposed. `original` stays pending "
                   "the owner's decision.")
    else:
        out.append(f"{selection_text}, applied in order {', '.join(order)}: "
                   f"**`{proposal}`**. This is a proposal for approval; `DEFAULT_CONFIG` is unchanged and the "
                   "held-out split has not been run.")
    out.append("")
    return "\n".join(out)


def _band_stats(scores, lo: float | None, hi: float | None) -> tuple[int, int, float | None]:
    group = [p for p in scores if (lo is None or p.opportunity_per_10min >= lo)
             and (hi is None or p.opportunity_per_10min < hi)]
    delays = [p.delay_ms / MINUTE_MS for p in group if p.delay_ms is not None]
    return sum(p.outcome == "correct" for p in group), len(group), (
        statistics.median(delays) if delays else None)


def render_holdout(dev: ConfigSummary, hold: ConfigSummary, cuts: tuple[float, float], commit: str,
                   protocol: str) -> str:
    """Final held-out report body: the frozen configuration on development and held-out seeds."""
    lo, hi = cuts

    def col(s: ConfigSummary) -> dict[str, str]:
        d = s.delays_min
        r = s.reason_pct()
        return {
            "Correct detections (recall, 95% Wilson CI)": _ci(s.correct, s.n),
            "Correct within 15 minutes": f"{s.correct_within}/{s.n}",
            "Missed": f"{s.count('miss')}/{s.n}",
            "Early detections": f"{s.count('early')}/{s.n}",
            "Median delay, correct detections (min)": _f(s.median_delay_min),
            "Mean delay (min)": _f(sum(d) / len(d) if d else None),
            "Delay range (min)": f"{_f(min(d) if d else None)}–{_f(max(d) if d else None)}",
            "Control false alarms (per control match)": f"{s.control_fa} ({s.control_fa / s.n:.2f})",
            "Control matches with ≥1 false alarm": _ci(s.control_matches_with_fa, s.n),
            "Treated non-target false alarms": str(s.treated_fa),
            "Insufficient evidence, all team-ticks": f"{s.insufficient_pct:.1f}%",
            "Insufficient evidence, target team after switch": f"{s.target_post_insufficient_pct:.1f}%",
            "…naming recent build-up shortfall": f"{r['recent_buildup']:.1f}%",
            "…naming a 5-minute-half shortfall": f"{r['half_buildup']:.1f}%",
            "…naming baseline shortfalls": f"{r['baseline_length'] + r['baseline_buildup']:.1f}%",
        }

    dc, hc = col(dev), col(hold)
    c = hold.config
    out = ["# Detector benchmark — final held-out evaluation", "",
           f"Frozen configuration `{hold.name}`, evaluated once on the {hold.n} held-out seed pairs. Harness commit "
           f"`{commit}`; protocol: {protocol}. Scoring rules: `docs/EVALUATION_PROTOCOL.md` section 4, unchanged.",
           "", f"Configuration: min_baseline_ms {c.min_baseline_ms // MINUTE_MS} min, min_baseline_buildup "
           f"{c.min_baseline_buildup}, min_recent_buildup {c.min_recent_buildup}, min_half_buildup "
           f"{c.min_half_buildup}, z_primary {c.z_primary}, z_support {c.z_support}, min_rate_ratio "
           f"{c.min_rate_ratio}, min_half_ratio {c.min_half_ratio}, persistence {c.persistence_ticks} ticks, "
           f"windows {c.long_window_ms // MINUTE_MS}/{c.short_window_ms // MINUTE_MS} min.", "",
           "## Results", "", f"| Measure | Development ({dev.n} pairs) | Held-out ({hold.n} pairs) |",
           "|---|---|---|"]
    out += [f"| {k} | {dc[k]} | {hc[k]} |" for k in dc]
    out += ["", "Development figures: the same frozen configuration re-run on the development seeds in the same "
            "invocation (must equal `recent8_z233` in `docs/BENCHMARK_DEV_RESULTS_3B1B.md`).", "",
            "## Breakdown by opponent build-up opportunities", "",
            "Opponent build-up passes per 10 minutes for the target team, switch to full time (public events). "
            f"Band edges fixed from the development data (protocol section 5): low < {lo:.1f} ≤ middle < {hi:.1f} "
            "≤ high.", "",
            "| Band | Dev correct | Dev median delay | Held-out correct | Held-out median delay |",
            "|---|---:|---:|---:|---:|"]
    for label, band in (("low", (None, lo)), ("middle", (lo, hi)), ("high", (hi, None))):
        dk, dn, dm = _band_stats(dev.scores, *band)
        hk, hn, hm = _band_stats(hold.scores, *band)
        out.append(f"| {label} | {dk}/{dn} | {_f(dm)} | {hk}/{hn} | {_f(hm)} |")
    out.append("")
    return "\n".join(out)


def render_worsening(summaries: Sequence[ConfigSummary], reference: str) -> str:
    ref = next(s for s in summaries if s.name == reference)
    out = ["## Changes relative to the original baseline", "",
           f"Per-seed comparison with `{reference}` on the same pairs. Lost = `{reference}` detected the switch "
           "correctly but this configuration missed it or fired early. Later = both correct, this one later. "
           "Extra FA = additional false alarms, summed over matches.", "",
           "| Config | Kept | Gained | Lost | Later | Extra control FA | Extra treated non-target FA |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for s in summaries:
        if s.name == reference:
            continue
        w = worsening(s, ref)
        out.append(f"| `{s.name}` | {w.kept} | {w.gained} | {w.lost} | {w.later} | {w.extra_control_fa} | "
                   f"{w.extra_treated_fa} |")
    out.append("")
    return "\n".join(out)


def render_details(split: str, summaries: Sequence[ConfigSummary]) -> str:
    out = [f"# PRIVATE — per-match benchmark details ({split})", "",
           "Contains hidden switch times. Never expose to the live system.", "",
           "| Seed | Switch (elapsed min) | Opp build-up /10 min | "
           + " | ".join(f"`{s.name}`" for s in summaries) + " |",
           "|---|---:|---:|" + "---|" * len(summaries)]
    for i, p in enumerate(summaries[0].scores):
        cells = []
        for s in summaries:
            q = s.scores[i]
            cell = q.outcome if q.delay_ms is None else f"correct +{q.delay_ms / MINUTE_MS:.1f}"
            if q.outcome == "early":
                cell += f" ({(q.detected_ms - q.switch_ms) / MINUTE_MS:.1f})"
            fa = q.control_false_alarms + q.treated_false_alarms
            cells.append(cell + (f", FA c{q.control_false_alarms}/t{q.treated_false_alarms}" if fa else ""))
        out.append(f"| {p.seed} | {p.switch_ms / MINUTE_MS:.1f} | {p.opportunity_per_10min:.1f} | "
                   + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)
