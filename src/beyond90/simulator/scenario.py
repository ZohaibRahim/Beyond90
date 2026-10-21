"""Hidden tactical scripts. The schedule is drawn from the seed, never from public data."""

from __future__ import annotations

import hashlib
import random

from beyond90.ground_truth import InterventionManifest, PressingChange, PressingIntensity, TeamBaseline
from beyond90.schemas import MatchSetup


def match_id_for_seed(seed: int) -> str:
    """Opaque public match id: does not reveal the seed (and so the hidden script)."""
    return "m-" + hashlib.sha256(f"beyond90-match-{seed}".encode()).hexdigest()[:12]


def pressing_switch_script(setup: MatchSetup, seed: int) -> InterventionManifest:
    """Away team starts in a low block and switches to a high press in the second half.

    The switch time is drawn uniformly from 53'-65' using a scenario RNG that is
    independent of the match-engine RNG.
    """
    rng = random.Random(f"beyond90-scenario-{seed}")
    clock_ms = rng.randrange(8 * 60_000, 20 * 60_000, 1000)
    home, away = setup.team_ids
    return InterventionManifest(
        match_id=setup.match_id,
        simulation_seed=seed,
        baselines=(
            TeamBaseline(team_id=home, pressing=PressingIntensity.MEDIUM),
            TeamBaseline(team_id=away, pressing=PressingIntensity.LOW),
        ),
        interventions=(
            PressingChange(
                intervention_id="iv-1", match_id=setup.match_id, team_id=away,
                effective_period=2, effective_clock_ms=clock_ms, intensity=PressingIntensity.HIGH,
                note="Away team abandons its low block and presses high.",
            ),
        ),
    )


def control_script(script: InterventionManifest) -> InterventionManifest:
    """Same baselines and seed with no interventions (for paired comparisons)."""
    return script.model_copy(update={"interventions": ()})
