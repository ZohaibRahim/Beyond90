"""OFFLINE evaluation harness: scores the public-data detector against hidden ground truth.

May import the simulator and ground truth. Live-side packages must never import it.
"""

from beyond90.benchmark.splits import DEV_SEEDS, HOLDOUT_SEEDS, HoldoutLockedError, seeds_for

__all__ = ["DEV_SEEDS", "HOLDOUT_SEEDS", "HoldoutLockedError", "seeds_for"]
