"""Run the detector benchmark.

- ``python -m beyond90.benchmark --split dev [--experiment 3b1|3b1b]``: development comparisons.
- ``python -m beyond90.benchmark --split holdout --unlock-holdout``: the FINAL held-out
  evaluation of the single frozen configuration (``DEFAULT_CONFIG``). It requires a
  clean git tree (the commit is recorded), refuses alternative configurations, and
  refuses to run if held-out results already exist (one run only).
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from beyond90.benchmark.report import render_details, render_holdout, render_summary, render_worsening
from beyond90.benchmark.scoring import (
    CANDIDATES,
    CANDIDATES_1B,
    FROZEN,
    ORDER_1B,
    opportunity_thirds,
    run_configs,
    select,
    select_1b,
)
from beyond90.benchmark.splits import DEV_SEEDS, HoldoutLockedError, seeds_for

HOLDOUT_OUT = Path("docs/BENCHMARK_HOLDOUT_RESULTS.md")
HOLDOUT_DETAILS = Path("reports/private/benchmark_holdout_details.md")
PROTOCOL_VERSION = "docs/EVALUATION_PROTOCOL.md sections 1–8 + Amendment 1 + frozen-configuration record"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def holdout_preflight(unlock: bool, experiment: str | None, out: Path, git=_git) -> str:
    """Every guard for the one held-out run; returns the commit being evaluated."""
    if not unlock:
        raise HoldoutLockedError("the held-out split needs --unlock-holdout")
    if experiment is not None:
        raise SystemExit("the held-out run evaluates only the frozen configuration; drop --experiment")
    if out.exists():
        raise SystemExit(f"{out} already exists: the held-out split has been run; it is run only once")
    if git("status", "--porcelain"):
        raise SystemExit("commit all changes before the held-out run (the evaluated commit is recorded)")
    return git("rev-parse", "--short", "HEAD")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--unlock-holdout", action="store_true")
    parser.add_argument("--experiment", choices=("3b1", "3b1b"), default=None,
                        help="dev only. 3b1 (default): minimum-data gates (protocol s.6); 3b1b: primary z (Amendment 1)")
    parser.add_argument("--out", type=Path, default=None, help="aggregate report (dev only)")
    parser.add_argument("--details", type=Path, default=None, help="PRIVATE per-match report (dev only)")
    args = parser.parse_args(argv)

    if args.split == "holdout":
        commit = holdout_preflight(args.unlock_holdout, args.experiment, HOLDOUT_OUT)
        hold = run_configs(seeds_for("holdout", allow_holdout=True), FROZEN)
        dev = run_configs(DEV_SEEDS, FROZEN)
        cuts = opportunity_thirds(dev[0].scores)  # band edges from development data (protocol s.5)
        HOLDOUT_OUT.write_text(render_holdout(dev[0], hold[0], cuts, commit, PROTOCOL_VERSION), encoding="utf-8")
        HOLDOUT_DETAILS.parent.mkdir(parents=True, exist_ok=True)
        HOLDOUT_DETAILS.write_text(render_details("holdout", hold), encoding="utf-8")
        for name, s in (("dev", dev[0]), ("holdout", hold[0])):
            print(f"{name:8s} correct {s.correct}/{s.n} within15 {s.correct_within} early {s.count('early')} "
                  f"control FA {s.control_fa} treated FA {s.treated_fa} median delay {s.median_delay_min}")
        print(f"commit {commit}\nwrote {HOLDOUT_OUT} and {HOLDOUT_DETAILS}")
        return

    experiment = args.experiment or "3b1"
    seeds = seeds_for("dev")
    suffix = "" if experiment == "3b1" else "_3B1B"
    out = args.out or Path(f"docs/BENCHMARK_DEV_RESULTS{suffix}.md")
    details = args.details or Path(f"reports/private/benchmark_dev_details{suffix.lower()}.md")
    if experiment == "3b1":
        summaries = run_configs(seeds, CANDIDATES)
        proposal = select(summaries)
        summary = render_summary("dev", summaries, proposal)
    else:
        summaries = run_configs(seeds, CANDIDATES_1B)
        proposal = select_1b(summaries)
        summary = render_summary(
            "dev", summaries, proposal, order=ORDER_1B, title="primary z comparison (Amendment 1)",
            notes=["`original` is the Stage 3A detector, re-run as a reference and reproducibility check; it is "
                   "not selectable. Selection follows protocol Amendment 1, fixed before this run."],
            selection_text="Selection rule (protocol Amendment 1)",
        ) + render_worsening(summaries, reference="original")
    for path, text in ((out, summary), (details, render_details("dev", summaries))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for s in summaries:
        print(f"{s.name:16s} correct {s.correct}/{s.n} early {s.count('early')} control FA {s.control_fa} "
              f"median delay {s.median_delay_min}")
    print(f"proposal: {proposal}\nwrote {out} and {details}")


if __name__ == "__main__":
    main()
