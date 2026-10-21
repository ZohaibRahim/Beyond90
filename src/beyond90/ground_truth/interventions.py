"""Hidden tactical-intervention schema, version 1.

Interventions are instructions the simulator applies to a team mid-match
(e.g. "start pressing high at 55:00"). They shape the generated events but are
never emitted with them. The evaluation harness compares them with what the
live system inferred to measure detection accuracy, false alarms and delay.

This module intentionally does not import the public event schema, and the
public schema does not import it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

INTERVENTION_SCHEMA_VERSION = "1.0.0"

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _InterventionBase(_Frozen):
    schema_version: Literal["1.0.0"] = INTERVENTION_SCHEMA_VERSION
    intervention_id: Identifier
    match_id: Identifier
    team_id: Identifier = Field(description="Team whose behaviour changes.")
    effective_period: Literal[1, 2]
    effective_clock_ms: int = Field(ge=0, description="Applies from this time in the period onward.")
    note: str | None = Field(default=None, max_length=500, description="Human-readable ground truth.")


class PressingIntensity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PressingChange(_InterventionBase):
    intervention_type: Literal["pressing_change"] = "pressing_change"
    intensity: PressingIntensity


class DefensiveLineChange(_InterventionBase):
    intervention_type: Literal["defensive_line_change"] = "defensive_line_change"
    line_height_m: float = Field(ge=15.0, le=60.0, description="Distance of back line from own goal.")


class Tempo(StrEnum):
    SLOW = "slow"
    NORMAL = "normal"
    FAST = "fast"


class TempoChange(_InterventionBase):
    intervention_type: Literal["tempo_change"] = "tempo_change"
    tempo: Tempo


TacticalIntervention = Annotated[
    Union[PressingChange, DefensiveLineChange, TempoChange],
    Field(discriminator="intervention_type"),
]


class InterventionManifest(_Frozen):
    """All hidden interventions for one simulated match, plus its seed."""

    schema_version: Literal["1.0.0"] = INTERVENTION_SCHEMA_VERSION
    match_id: Identifier
    simulation_seed: int = Field(ge=0)
    interventions: tuple[TacticalIntervention, ...] = ()

    @model_validator(mode="after")
    def _check_interventions(self) -> InterventionManifest:
        ids = [i.intervention_id for i in self.interventions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate intervention_id")
        if any(i.match_id != self.match_id for i in self.interventions):
            raise ValueError("every intervention must belong to the manifest's match")
        times = [(i.effective_period, i.effective_clock_ms) for i in self.interventions]
        if times != sorted(times):
            raise ValueError("interventions must be ordered by effective time")
        return self
