"""The live application's ONLY way to read match files from disk.

Reads are confined to a match's ``public/`` directory. Any path that resolves
outside it, or that passes through a directory named ``private``, is refused,
so private evaluation records cannot be loaded by the live runtime even by
mistake (e.g. ``public/../private/...`` or a symlink).
"""

from __future__ import annotations

from pathlib import Path

from beyond90.schemas import EventAdapter, MatchEvent, MatchSetup

PUBLIC_DIR = "public"
PUBLIC_FILES = ("match_setup.json", "events.jsonl")


class PrivateDataAccessError(PermissionError):
    pass


def _checked(path: Path, public_root: Path) -> Path:
    resolved = path.resolve()
    if any(part.lower() == "private" for part in resolved.parts):
        raise PrivateDataAccessError(f"refusing to read private data: {path}")
    if resolved.parent != public_root or resolved.name not in PUBLIC_FILES:
        raise PrivateDataAccessError(f"not a public match file: {path}")
    return resolved


def read_public_file(match_dir: Path, name: str) -> str:
    public_root = (Path(match_dir) / PUBLIC_DIR).resolve()
    if any(part.lower() == "private" for part in public_root.parts):
        raise PrivateDataAccessError(f"refusing to read private data: {match_dir}")
    return _checked(public_root / name, public_root).read_text(encoding="utf-8")


def load_public_match(match_dir: Path) -> tuple[MatchSetup, list[MatchEvent]]:
    setup = MatchSetup.model_validate_json(read_public_file(match_dir, "match_setup.json"))
    lines = read_public_file(match_dir, "events.jsonl").splitlines()
    return setup, [EventAdapter.validate_json(line) for line in lines if line.strip()]
