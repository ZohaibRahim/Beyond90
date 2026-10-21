"""Simulate one match: ``python -m beyond90.simulator --seed 42``."""

from __future__ import annotations

import argparse
from pathlib import Path

from beyond90.simulator.engine import simulate_match
from beyond90.simulator.output import write_outputs
from beyond90.simulator.report import render_report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)

    result = simulate_match(args.seed)
    paths = write_outputs(result, args.out)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = args.report_dir / f"match_report_seed{args.seed}.md"
    report.write_text(render_report(result), encoding="utf-8")
    for name, path in {**paths, "report": report}.items():
        print(f"{name:13s} {path}")


if __name__ == "__main__":
    main()
