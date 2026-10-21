"""Simulate one match: ``python -m beyond90.simulator --seed 42``.

Writes public data + a public report, and SEPARATELY the private ground truth and
private evaluation record. ``--review N`` also writes a private paired-control
review of the intervention over seeds 0..N-1.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from beyond90.reporting import render_match_report
from beyond90.simulator.engine import simulate_match
from beyond90.simulator.evaluation import intervention_review, render_evaluation_record
from beyond90.simulator.output import write_outputs
from beyond90.simulator.scenario import control_script


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--review", type=int, default=0, help="number of seeds for the intervention review")
    parser.add_argument("--control", action="store_true",
                        help="also write the paired no-intervention control match to <match_id>-control/")
    args = parser.parse_args(argv)

    result = simulate_match(args.seed)
    paths = write_outputs(result, args.out)
    public_dir, private_dir = args.reports / "public", args.reports / "private"
    public_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    paths["public_report"] = public_dir / f"match_report_seed{args.seed}.md"
    paths["public_report"].write_text(render_match_report(result.setup, result.events), encoding="utf-8")
    paths["private_record"] = private_dir / f"evaluation_seed{args.seed}.md"
    paths["private_record"].write_text(render_evaluation_record(result), encoding="utf-8")
    if args.control:
        control = simulate_match(args.seed, control_script(result.ground_truth.script))
        control_paths = write_outputs(control, args.out, f"{result.setup.match_id}-control")
        paths["control_events"] = control_paths["events"]
        paths["control_report"] = public_dir / f"match_report_seed{args.seed}_control.md"
        paths["control_report"].write_text(render_match_report(control.setup, control.events), encoding="utf-8")
    if args.review:
        paths["private_review"] = private_dir / "intervention_review.md"
        paths["private_review"].write_text(intervention_review(range(args.review)), encoding="utf-8")
    for name, path in paths.items():
        print(f"{name:15s} {path}")


if __name__ == "__main__":
    main()
