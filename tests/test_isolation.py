"""Enforce the information barrier between hidden ground truth and live analysis."""

import ast
from pathlib import Path

import pytest

from beyond90.ground_truth import interventions
from beyond90.schemas import events

SRC = Path(__file__).resolve().parents[1] / "src" / "beyond90"
HIDDEN = "beyond90.ground_truth"

# Every live-side package. Add new ones here (agents, api, render, ...).
GUARDED_PACKAGES = ["schemas", "analytics"]


def _imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _guarded_files():
    return [f for pkg in GUARDED_PACKAGES for f in sorted((SRC / pkg).rglob("*.py"))]


def test_guarded_packages_exist():
    for pkg in GUARDED_PACKAGES:
        assert (SRC / pkg / "__init__.py").is_file(), pkg


@pytest.mark.parametrize("path", _guarded_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_live_side_never_imports_ground_truth(path):
    # `from beyond90 import ground_truth` is recorded as "beyond90.ground_truth" too.
    leaks = {m for m in _imported_modules(path) if m == HIDDEN or m.startswith(HIDDEN + ".")}
    assert not leaks, f"{path} imports hidden ground truth: {leaks}"


def test_live_side_has_no_dynamic_import_of_ground_truth():
    for path in _guarded_files():
        assert "ground_truth" not in path.read_text(encoding="utf-8"), path


def test_hidden_schema_does_not_depend_on_public_schema():
    assert "beyond90.schemas" not in _imported_modules(Path(interventions.__file__))


def test_event_schema_has_no_intervention_fields():
    forbidden = {"intervention", "instruction", "tactic", "seed", "ground_truth"}
    for model in [events.PassEvent, events.ShotEvent, events.TackleEvent, events.PressureEvent,
                  events.InterceptionEvent, events.PossessionChangeEvent, events.SubstitutionEvent]:
        for field in model.model_fields:
            assert not any(word in field for word in forbidden), (model.__name__, field)
