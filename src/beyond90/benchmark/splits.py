"""Frozen development / held-out seed split (docs/EVALUATION_PROTOCOL.md section 2)."""

from __future__ import annotations

import random

SPLIT_SALT = "beyond90-benchmark-split-v1"
SEED_POOL = range(1000, 10000)  # excludes seed 42 and seeds 0-29 inspected in Stages 2-3A


def _draw() -> tuple[list[int], list[int]]:
    seeds = random.Random(SPLIT_SALT).sample(SEED_POOL, 60)
    return sorted(seeds[:30]), sorted(seeds[30:])


# Frozen literal copies; tests check they match the documented draw.
DEV_SEEDS = (1249, 1804, 2174, 2201, 2375, 2614, 3370, 3781, 3899, 4095, 4364, 4487, 4536, 4538, 4920,
             5364, 5794, 5868, 5990, 6039, 6112, 6535, 6663, 6954, 7118, 7352, 8595, 8860, 9652, 9914)
HOLDOUT_SEEDS = (1076, 1126, 1390, 1627, 2000, 2121, 2205, 2211, 2619, 2855, 3430, 3546, 3555, 3600, 3783,
                 3993, 4340, 4393, 4618, 4900, 5336, 6229, 7106, 7287, 7301, 7331, 7730, 7914, 8365, 9789)


class HoldoutLockedError(RuntimeError):
    pass


def seeds_for(split: str, *, allow_holdout: bool = False) -> tuple[int, ...]:
    if split == "dev":
        return DEV_SEEDS
    if split == "holdout":
        if not allow_holdout:
            raise HoldoutLockedError("the held-out split is locked until a configuration is approved")
        return HOLDOUT_SEEDS
    raise ValueError(f"unknown split {split!r}")
