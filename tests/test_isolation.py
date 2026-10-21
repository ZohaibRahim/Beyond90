"""Enforce the information barrier between hidden ground truth and live analysis."""

import ast
import json
from pathlib import Path

import pytest

from beyond90.ground_truth import interventions
from beyond90.reporting import render_match_report
from beyond90.schemas import EVENT_MODELS
from beyond90.simulator import simulate_match, write_outputs

SRC = Path(__file__).resolve().parents[1] / "src" / "beyond90"
FORBIDDEN = ("beyond90.ground_truth", "beyond90.simulator", "beyond90.benchmark")

# Every live-side package. Add new ones here (agents, api, render, ...).
GUARDED_PACKAGES = ["schemas", "analytics", "reporting", "live", "detection"]


def _imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            # `from beyond90 import ground_truth` is recorded as "beyond90.ground_truth" too.
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _guarded_files():
    return [f for pkg in GUARDED_PACKAGES for f in sorted((SRC / pkg).rglob("*.py"))]


def test_guarded_packages_exist():
    for pkg in GUARDED_PACKAGES:
        assert (SRC / pkg / "__init__.py").is_file(), pkg


@pytest.mark.parametrize("path", _guarded_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_live_side_never_imports_hidden_or_simulator(path):
    leaks = {m for m in _imported_modules(path) for bad in FORBIDDEN if m == bad or m.startswith(bad + ".")}
    assert not leaks, f"{path} imports hidden modules: {leaks}"


@pytest.mark.parametrize("path", _guarded_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_live_side_has_no_dynamic_imports(path):
    text = path.read_text(encoding="utf-8")
    for needle in ("importlib", "__import__", "ground_truth.json", *FORBIDDEN):
        assert needle not in text, f"{path} mentions {needle}"


def test_hidden_schema_does_not_depend_on_public_schema():
    assert not any(m.startswith("beyond90.schemas") for m in _imported_modules(Path(interventions.__file__)))


def test_event_schema_has_no_hidden_or_computed_fields():
    forbidden = {"intervention", "instruction", "tactic", "press_", "intensity", "seed", "ground_truth",
                 "xg", "difficulty", "intent", "probability"}
    for model in EVENT_MODELS:
        for field in model.model_fields:
            assert not any(word in field for word in forbidden), (model.__name__, field)


def test_public_output_reveals_no_tactical_settings(tmp_path):
    result = simulate_match(11)
    paths = write_outputs(result, tmp_path)
    public_text = paths["setup"].read_text(encoding="utf-8") + paths["events"].read_text(encoding="utf-8")
    script = result.ground_truth.script
    hidden_tokens = {"intervention", "pressing", "intensity", "baseline", "tactic", "seed", "note",
                     *(i.intervention_id for i in script.interventions)}
    lowered = public_text.lower()
    for token in hidden_tokens:
        assert token not in lowered, token
    # Every public event key is a schema field; nothing extra is serialized.
    allowed = {f for m in EVENT_MODELS for f in m.model_fields}
    for line in paths["events"].read_text(encoding="utf-8").splitlines():
        assert set(json.loads(line)) <= allowed
    assert str(script.simulation_seed) not in result.setup.match_id


HIDDEN_WORDS = ("intervention", "pressing", "intensity", "baseline", "tactic", "seed", "ground truth",
                "ground_truth", "low block", "presses high", "press high", "hidden")


def test_public_report_contains_no_hidden_information():
    result = simulate_match(42)
    report = render_match_report(result.setup, result.events).lower()
    for word in HIDDEN_WORDS:
        assert word not in report, word
    for iv in result.ground_truth.script.interventions:
        assert iv.intervention_id not in report


def test_public_report_renderer_takes_only_public_inputs():
    import inspect

    assert list(inspect.signature(render_match_report).parameters) == ["setup", "events", "event_sample"]
