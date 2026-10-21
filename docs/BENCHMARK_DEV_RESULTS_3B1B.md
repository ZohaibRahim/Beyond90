# Detector benchmark — dev split — primary z comparison (Amendment 1)

`original` is the Stage 3A detector, re-run as a reference and reproducibility check; it is not selectable. Selection follows protocol Amendment 1, fixed before this run.

30 seeds, each a treated match (hidden LOW→HIGH press switch for the away team in 53'–65') and its paired no-intervention control. Scoring and selection follow `docs/EVALUATION_PROTOCOL.md`, fixed before this run. All configurations are reported.

z values are approximate heuristics (overlapping minute-by-minute windows are strongly dependent); the error rates below are the empirical measure.

## Headline results

| Config | Correct | Correct ≤15 min | Early | Missed | Median delay (min) | Mean | Min–max | Control false alarms | Controls with ≥1 FA | Treated non-target FA | Eligible |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| `original` | 10/30 (33%, 95% CI 19–51%) | 5 | 0 | 20 | 14.6 | 15.2 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent8_z233` | 12/30 (40%, 95% CI 25–58%) | 7 | 0 | 18 | 13.8 | 14.9 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent8_z200` | 13/30 (43%, 95% CI 27–61%) | 7 | 1 | 16 | 14.4 | 16.5 | 5.1–28.6 | 1 (0.03/match) | 1/30 (3%, 95% CI 1–17%) | 0 | yes |
| `recent8_z164` | 12/30 (40%, 95% CI 25–58%) | 6 | 2 | 16 | 15.1 | 17.4 | 8.4–28.6 | 4 (0.13/match) | 3/30 (10%, 95% CI 3–26%) | 0 | no |

Eligible = control false alarms ≤ 0.10 per match and ≤ 1 early detection.

## Configurations

| Config | min_baseline_ms | min_baseline_buildup | min_recent_buildup | min_half_buildup | z_primary |
|---|---:|---:|---:|---:|---:|
| `original` | 20 min | 40 | 15 | 6 | 2.33 |
| `recent8_z233` | 20 min | 40 | 8 | 3 | 2.33 |
| `recent8_z200` | 20 min | 40 | 8 | 3 | 2.00 |
| `recent8_z164` | 20 min | 40 | 8 | 3 | 1.64 |

All other thresholds as in Stage 3A (corroboration z 1.64, ratio 1.5, half ratio 1.2, 3-tick persistence).

## Insufficient evidence

| Config | All team-ticks | Target team after switch | …baseline length | …baseline build-up | …recent build-up | …5-min half |
|---|---:|---:|---:|---:|---:|---:|
| `original` | 75.7% | 63.6% | 0.0% | 0.0% | 51.5% | 58.3% |
| `recent8_z233` | 51.0% | 23.7% | 0.0% | 0.0% | 12.3% | 22.2% |
| `recent8_z200` | 51.0% | 23.7% | 0.0% | 0.0% | 12.3% | 22.2% |
| `recent8_z164` | 51.0% | 23.7% | 0.0% | 0.0% | 12.3% | 22.2% |

Reason columns: share of target-team post-switch ticks naming that shortfall (a tick can name several).

## Opportunity availability

Opponent build-up passes per 10 minutes for the target team, switch to full time (public events). Thirds of the 30 treated matches: low < 14.3 ≤ middle < 17.0 ≤ high.

| Config | Low: correct | Low: median delay | Middle: correct | Middle: median delay | High: correct | High: median delay |
|---|---:|---:|---:|---:|---:|---:|
| `original` | 0/10 | n/a | 3/10 | 17.4 | 7/10 | 13.2 |
| `recent8_z233` | 2/10 | 17.3 | 3/10 | 14.4 | 7/10 | 13.2 |
| `recent8_z200` | 2/10 | 17.3 | 5/10 | 15.8 | 6/10 | 11.0 |
| `recent8_z164` | 2/10 | 17.3 | 5/10 | 15.8 | 5/10 | 13.2 |

## Proposed configuration

Selection rule (protocol Amendment 1), applied in order recent8_z233, recent8_z200, recent8_z164: **`recent8_z233`**. This is a proposal for approval; `DEFAULT_CONFIG` is unchanged and the held-out split has not been run.
## Changes relative to the original baseline

Per-seed comparison with `original` on the same pairs. Lost = `original` detected the switch correctly but this configuration missed it or fired early. Later = both correct, this one later. Extra FA = additional false alarms, summed over matches.

| Config | Kept | Gained | Lost | Later | Extra control FA | Extra treated non-target FA |
|---|---:|---:|---:|---:|---:|---:|
| `recent8_z233` | 10 | 2 | 0 | 0 | 0 | 0 |
| `recent8_z200` | 9 | 4 | 1 | 0 | 1 | 0 |
| `recent8_z164` | 8 | 4 | 2 | 0 | 4 | 0 |

## Selection walkthrough (Amendment 1, applied as written)

1. **Eligibility:**
   - `recent8_z233`: 0 control false alarms, 0 early. Eligible.
   - `recent8_z200`: 1 false alarm, 1 early. Eligible.
   - `recent8_z164`: 4 control false alarms (limit 3) and 2 early (limit 1). **Not eligible.**
2. **Start:** `recent8_z233` (12 correct).
3. **`recent8_z200`:** 13 correct, a gain of +1, below the meaningful threshold of +2. Tie-breakers:
   - detections within 15 minutes: 7 vs 7, equal;
   - total false alarms (control + treated non-target): 1 vs 0, worse.

   So `recent8_z233` is kept.
4. **Result:** `recent8_z233`.

## Unfavourable results (not hidden)

- **Lowering z did not raise recall meaningfully.**
  - z 2.00 nets one extra detection (13 vs 12). It gains two very late detections, at about +28 minutes, and loses one switch to an early alarm.
  - z 1.64 nets none (12) and adds four control false alarms in three matches.
- **Early alarms appear in pairs.** Both early detections are false alarms before the switch that also appear in the paired control. One fired about 27 minutes before the switch, the other about 9. Treated and control streams are identical before the switch.
  - Under z 2.00, a switch that `original` and `recent8_z233` detected at +10.3 minutes is lost.
  - Under z 1.64, a second switch that every other configuration detected at +5.1 minutes is also lost.
- **Delays get longer as z falls:** median 13.8 → 14.4 → 15.1 minutes, mean 14.9 → 16.5 → 17.4. The extra detections are late ones. Lower z does find some switches sooner: two matches by 4.0 and 7.0 minutes.
- **High-opportunity matches get worse** with lower z: 7/10 → 6/10 → 5/10, because of the early alarms.
- **Insufficient evidence is the same for all three z values** (gates unchanged): 23.7% of target-team post-switch ticks.
- **Against the original Stage 3A detector:** `recent8_z233` loses no detection, adds no false alarm and is never later. It gains 2 detections, and 2 kept detections come 3.0 and 5.0 minutes sooner.
- **Recall remains low** for every configuration: at most 43% (95% CI 27–61%). 16 of the 30 switches are not detected by any configuration in this comparison.
