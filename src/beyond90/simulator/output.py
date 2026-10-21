"""Write simulation output: a public directory and a SEPARATE private directory.

Layout under ``out_dir/<match_id>/``:
- ``public/match_setup.json``  team sheets and orientation (observable)
- ``public/events.jsonl``       one public event per line, in sequence order
- ``private/ground_truth.json`` hidden script + where it took effect (evaluation only)
"""

from __future__ import annotations

from pathlib import Path

from beyond90.simulator.engine import SimulationResult


def write_outputs(result: SimulationResult, out_dir: Path, name: str | None = None) -> dict[str, Path]:
    """``name`` overrides the directory name (default: the match id), e.g. for a paired control."""
    root = Path(out_dir) / (name or result.setup.match_id)
    public, private = root / "public", root / "private"
    public.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    paths = {
        "setup": public / "match_setup.json",
        "events": public / "events.jsonl",
        "ground_truth": private / "ground_truth.json",
    }
    paths["setup"].write_text(result.setup.model_dump_json(indent=2), encoding="utf-8")
    paths["events"].write_text("".join(e.model_dump_json() + "\n" for e in result.events), encoding="utf-8")
    paths["ground_truth"].write_text(result.ground_truth.model_dump_json(indent=2), encoding="utf-8")
    return paths
