import pytest
from pydantic import ValidationError

from beyond90.ground_truth import (
    DefensiveLineChange,
    InterventionManifest,
    PressingChange,
    TempoChange,
)


def _common(iid="i1", period=2, clock_ms=600_000, **kw):
    return {"intervention_id": iid, "match_id": "m001", "team_id": "river_utd",
            "effective_period": period, "effective_clock_ms": clock_ms, **kw}


def _press(iid="i1", period=2, clock_ms=600_000, **kw):
    return {"intervention_type": "pressing_change", "intensity": "high",
            **_common(iid, period, clock_ms), **kw}


def test_manifest_parses_discriminated_interventions():
    m = InterventionManifest.model_validate({
        "match_id": "m001", "simulation_seed": 42,
        "interventions": [
            _press("i1", period=1, clock_ms=1_200_000),
            _common("i2", clock_ms=300_000, intervention_type="defensive_line_change", line_height_m=45.0),
            _common("i3", clock_ms=900_000, intervention_type="tempo_change", tempo="fast"),
        ],
    })
    assert [type(i) for i in m.interventions] == [PressingChange, DefensiveLineChange, TempoChange]


def test_manifest_json_round_trip():
    m = InterventionManifest(match_id="m001", simulation_seed=7,
                             interventions=(PressingChange.model_validate(_press()),))
    assert InterventionManifest.model_validate_json(m.model_dump_json()) == m


def test_unknown_intervention_type_rejected():
    with pytest.raises(ValidationError):
        InterventionManifest.model_validate(
            {"match_id": "m001", "simulation_seed": 1,
             "interventions": [_press(intervention_type="formation_change")]})


def test_duplicate_intervention_ids_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        InterventionManifest.model_validate(
            {"match_id": "m001", "simulation_seed": 1,
             "interventions": [_press("i1", clock_ms=1), _press("i1", clock_ms=2)]})


def test_intervention_for_other_match_rejected():
    with pytest.raises(ValidationError, match="belong"):
        InterventionManifest.model_validate(
            {"match_id": "m001", "simulation_seed": 1, "interventions": [_press(match_id="m999")]})


def test_interventions_must_be_time_ordered():
    with pytest.raises(ValidationError, match="ordered"):
        InterventionManifest.model_validate(
            {"match_id": "m001", "simulation_seed": 1,
             "interventions": [_press("i1", period=2), _press("i2", period=1)]})


@pytest.mark.parametrize("bad", [{"simulation_seed": -1}, {"extra_field": True}])
def test_manifest_constraints(bad):
    with pytest.raises(ValidationError):
        InterventionManifest.model_validate({"match_id": "m001", "simulation_seed": 1} | bad)


def test_defensive_line_bounds():
    with pytest.raises(ValidationError):
        DefensiveLineChange.model_validate(_common(line_height_m=80.0))
