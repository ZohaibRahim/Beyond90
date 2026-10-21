"""Synthetic match simulator. May read hidden ground truth; the live system must not import this package."""

from beyond90.simulator.engine import SIMULATOR_VERSION, SimulationResult, simulate_match
from beyond90.simulator.output import write_outputs
from beyond90.simulator.scenario import control_script, match_id_for_seed, pressing_switch_script

__all__ = [
    "SIMULATOR_VERSION",
    "SimulationResult",
    "control_script",
    "match_id_for_seed",
    "pressing_switch_script",
    "simulate_match",
    "write_outputs",
]
