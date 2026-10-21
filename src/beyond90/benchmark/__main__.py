"""Run the detector benchmark: ``python -m beyond90.benchmark --split dev``.

The held-out split is refused unless ``--unlock-holdout`` is given (only after the
owner approves a configuration; see docs/EVALUATION_PROTOCOL.md).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from beyond90.benchmark.report import render_details, render_summary
from beyond90.benchmark.scoring import run_configs, select
from beyond90.benchmark.splits import seeds_for


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--unlock-holdout", action="store_true")
    parser.add_argument("--out", type=Path, default=None, help="aggregate report (default docs/<split> results)")
    parser.add_argument("--details", type=Path, default=None, help="PRIVATE per-match report")
    args = parser.parse_args(argv)

    seeds = seeds_for(args.split, allow_holdout=args.unlock_holdout)
    out = args.out or Path(f"docs/BENCHMARK_{args.split.upper()}_RESULTS.md")
    details = args.details or Path(f"reports/private/benchmark_{args.split}_details.md")
    summaries = run_configs(seeds)
    proposal = select(summaries)
    for path, text in ((out, render_summary(args.split, summaries, proposal)),
                       (details, render_details(args.split, summaries))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for s in summaries:
        print(f"{s.name:16s} correct {s.correct}/{s.n} early {s.count('early')} control FA {s.control_fa} "
              f"median delay {s.median_delay_min}")
    print(f"proposal: {proposal}\nwrote {out} and {details}")


if __name__ == "__main__":
    main()
