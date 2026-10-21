# Detector evaluation protocol (Stage 3B)

This document was written and committed **before** any development benchmark run. Rules
changed after results are seen must be recorded below as amendments, with reasons.

## 1. What is evaluated

The pressing-change detector in `beyond90.detection` (`detect(setup, events, config)`),
run on public events only. The offline harness `beyond90.benchmark` is the only code
that combines detector output with hidden ground truth. It passes the detector nothing
but the public `MatchSetup` and the public event list. Guarded live-side packages may not
import `beyond90.benchmark` (`tests/test_isolation.py`).

## 2. Scenarios and frozen split

- Each benchmark unit is a pair of matches for one seed:
  - **Treated:** the standard hidden script (`pressing_switch_script`). Away team Kestrel Bay starts LOW and switches to HIGH pressing at a random time from 53' to 65'. Home team stays MEDIUM throughout.
  - **Control:** the same seed, baselines and engine RNG with no intervention (`control_script`).
- Split (`beyond90/benchmark/splits.py`): 60 distinct seeds drawn once with `random.Random("beyond90-benchmark-split-v1").sample(range(1000, 10000), 60)`. The first 30 are **development**, the last 30 **held-out**.
  - The range excludes seed 42 and seeds 0–29, which were inspected in Stages 2–3A.
  - A test pins both lists.
- **The held-out split is locked.** The harness refuses it unless explicitly unlocked (`allow_holdout=True` / `--unlock-holdout`). It may be run **once**, only after the owner approves a final configuration, and its results are reported whatever they are.

Known scope limit: every treated match contains the same kind of change (away team, increase, second half). So this benchmark measures detection of a LOW→HIGH press switch and false alarms in controls. It does not measure decreases, home-team changes, first-half changes or other tactics.

## 3. Ground-truth time of the change

- `T0` is the elapsed match time (period-1 length + period-2 clock) of the first event the intervention affected: `GroundTruthRecord.applied[0].first_event_sequence`, located in the treated stream.
- The target is `(intervention team, direction = increase)`.

## 4. Scoring rules (per treated match)

Take the target team's first `increase` finding, detected at elapsed time `t`:

| Outcome | Rule |
|---|---|
| **Correct detection** | `t >= T0`. Delay = `t - T0`. Also reported: correct within 15 minutes (`t - T0 <= 15 min`). |
| **Early detection** | `t < T0`. Not correct: the detector reports one finding per team and direction, so an early finding pre-empts a later correct one. Counted separately, not as a false alarm. |
| **Miss** | No target-team `increase` finding at all. |

**False alarms:**
- Every finding in a control match.
- Every finding in a treated match other than the target team's increase (the other team, or the target team's decrease).

Treated and control streams are identical before `T0`, so findings before `T0` appear in both. Control false alarms are the primary false-alarm measure.

## 5. Reported measures (every configuration, successful or not)

- **Recall:** correct / 30, with a Wilson 95% interval; also recall within 15 minutes.
- **Detection delay** over correct detections: median, mean, min, max.
- **Early detections:** count.
- **Control false alarms:** total, per control match, and the number of control matches with at least one false alarm (Wilson 95% interval).
- **Treated-match non-target false alarms:** total.
- **Insufficient evidence:** percentage of all team-ticks with status `insufficient_evidence` (treated and control). Also the percentage for target-team ticks after `T0`, broken down by shortfall reason (baseline length, baseline build-up passes, recent build-up passes, a 5-minute half).
- **Opportunity availability:** opponent build-up passes per 10 minutes for the target team from `T0` to full time, from public events.
  - Treated matches are split into thirds (low / middle / high opportunity) by that rate, with recall and median delay reported per third.
  - Thirds are set from the development data. They describe the results; they are not used for selection.

## 6. Configurations compared (development seeds only)

Only the **minimum-data** thresholds vary. The statistical thresholds (z 2.33 / 1.64, ratio 1.5, half ratio 1.2, 3-tick persistence) stay at their Stage 3A values.

| Name | min_baseline_ms | min_baseline_buildup | min_recent_buildup | min_half_buildup | Rationale |
|---|---:|---:|---:|---:|---|
| A `original` | 20 min | 40 | 15 | 6 | Stage 3A config, unchanged |
| B `recent12` | 20 min | 40 | 12 | 5 | Mild relaxation of the recent-window minimum |
| C `recent10` | 20 min | 40 | 10 | 4 | Moderate relaxation |
| D `recent8` | 20 min | 40 | 8 | 3 | Aggressive relaxation; expected to admit noise (included to see where false alarms start) |
| E `recent10_base30` | 15 min | 30 | 10 | 4 | C plus a shorter, smaller baseline |

Why these were chosen: in the Stage 3A seed-42 run, most of the post-switch period was `insufficient_evidence` because the recent build-up minimum was not met. Seed 42 is excluded from both splits. No development result informed this list.

## 7. Selection rule (decided before running)

1. **Eligible** configurations meet both:
   - at most 0.10 control false alarms per match (at most 3 over 30 controls);
   - at most 1 early detection.
2. Order the eligible configurations from most to least conservative: A, B, C, E, D.
3. Start with the most conservative eligible one as the current choice. Each less conservative configuration replaces it only if it:
   - **(a)** detects at least 2 more matches correctly; or
   - **(b)** has equal or better recall and a median delay at least 2 minutes shorter.

   Small differences (one match, or under 2 minutes) do not justify admitting more noise.
4. If no configuration is eligible, recommend none: report that, and keep A pending the owner's decision.

The chosen configuration is a **proposal** for the owner's approval. It is not adopted as `DEFAULT_CONFIG` before approval and the held-out run.

## 8. Things the benchmark must not do

- Retune the simulator, edit scenario scripts or ground truth, or change seeds to improve results.
- Run the held-out split before approval.
- Add configurations after seeing development results without recording an amendment.

## Amendments

None.
