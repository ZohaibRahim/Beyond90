"""Run the detector benchmark: ``python -m beyond90.benchmark --split dev``.

The held-out split is refused unless ``--unlock-holdout`` is given (only after the
owner approves a configuration; see docs/EVALUATION_PROTOCOL.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from beyond90.benchmark.report import render_details, render_summary, render_worsening
from beyond90.benchmark.scoring import CANDIDATES, CANDIDATES_1B, ORDER_1B, run_configs, select, select_1b
from beyond90.benchmark.splits import seeds_for


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--unlock-holdout", action="store_true")
    parser.add_argument("--experiment", choices=("3b1", "3b1b"), default="3b1",
                        help="3b1: minimum-data gates (protocol s.6); 3b1b: primary z (Amendment 1)")
    parser.add_argument("--out", type=Path, default=None, help="aggregate report (default docs/<split> results)")
    parser.add_argument("--details", type=Path, default=None, help="PRIVATE per-match report")
    args = parser.parse_args(argv)

    seeds = seeds_for(args.split, allow_holdout=args.unlock_holdout)
    suffix = "" if args.experiment == "3b1" else "_3B1B"
    out = args.out or Path(f"docs/BENCHMARK_{args.split.upper()}_RESULTS{suffix}.md")
    details = args.details or Path(f"reports/private/benchmark_{args.split}_details{suffix.lower()}.md")
    if args.experiment == "3b1":
        summaries = run_configs(seeds, CANDIDATES)
        proposal = select(summaries)
        summary = render_summary(args.split, summaries, proposal)
    else:
        summaries = run_configs(seeds, CANDIDATES_1B)
        proposal = select_1b(summaries)
        summary = render_summary(
            args.split, summaries, proposal, order=ORDER_1B, title="primary z comparison (Amendment 1)",
            notes=["`original` is the Stage 3A detector, re-run as a reference and reproducibility check; it is "
                   "not selectable. Selection follows protocol Amendment 1, fixed before this run."],
            selection_text="Selection rule (protocol Amendment 1)",
        ) + render_worsening(summaries, reference="original")
    for path, text in ((out, summary), (details, render_details(args.split, summaries))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for s in summaries:
        print(f"{s.name:16s} correct {s.correct}/{s.n} early {s.count('early')} control FA {s.control_fa} "
              f"median delay {s.median_delay_min}")
    print(f"proposal: {proposal}\nwrote {out} and {details}")


if __name__ == "__main__":
    main()
