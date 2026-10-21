"""Run pressing-change detection on a public match directory.

``python -m beyond90.detection data/generated/<match> --out reports/public/detection.md``
Reads only ``<match>/public/`` via ``beyond90.live``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from beyond90.detection.detector import detect
from beyond90.detection.evidence import finding_evidence
from beyond90.detection.report import render_detection_report
from beyond90.live import load_public_match


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Markdown report path")
    parser.add_argument("--json", type=Path, help="optional JSON output of the full detection result")
    parser.add_argument("--evidence", type=Path, help="optional JSON output of the full evidence per finding")
    parser.add_argument("--label", default="")
    args = parser.parse_args(argv)

    setup, events = load_public_match(args.match_dir)
    result = detect(setup, events)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_detection_report(setup, result, args.label), encoding="utf-8")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    if args.evidence:
        evidence = [finding_evidence(setup, events, f).model_dump(mode="json") for f in result.findings]
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    for f in result.findings:
        print(f"{f.team_id} {f.direction} at P{f.detected_period} {f.detected_clock_ms / 60_000:.0f}' "
              f"({len(f.supporting_event_ids)} supporting events)")
    if not result.findings:
        print("no findings")


if __name__ == "__main__":
    main()
