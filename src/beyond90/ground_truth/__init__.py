"""HIDDEN ground truth. Import ONLY from the simulator and the offline evaluation harness.

Live analytics, AI agents, APIs and the frontend must never import this package;
``tests/test_isolation.py`` enforces the boundary.
"""

from beyond90.ground_truth.interventions import (
    INTERVENTION_SCHEMA_VERSION,
    DefensiveLineChange,
    InterventionManifest,
    PressingChange,
    PressingIntensity,
    TacticalIntervention,
    TempoChange,
    Tempo,
)

__all__ = [
    "INTERVENTION_SCHEMA_VERSION",
    "DefensiveLineChange",
    "InterventionManifest",
    "PressingChange",
    "PressingIntensity",
    "TacticalIntervention",
    "Tempo",
    "TempoChange",
]
