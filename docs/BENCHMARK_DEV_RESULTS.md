# Detector benchmark — dev split

30 seeds, each a treated match (hidden LOW→HIGH press switch for the away team in 53'–65') and its paired no-intervention control. Scoring and selection follow `docs/EVALUATION_PROTOCOL.md`, fixed before this run. All configurations are reported.

z values are approximate heuristics (overlapping minute-by-minute windows are strongly dependent); the error rates below are the empirical measure.

## Headline results

| Config | Correct | Correct ≤15 min | Early | Missed | Median delay (min) | Mean | Min–max | Control false alarms | Controls with ≥1 FA | Treated non-target FA | Eligible |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| `original` | 10/30 (33%, 95% CI 19–51%) | 5 | 0 | 20 | 14.6 | 15.2 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent12` | 10/30 (33%, 95% CI 19–51%) | 5 | 0 | 20 | 14.3 | 14.8 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent10` | 10/30 (33%, 95% CI 19–51%) | 6 | 0 | 20 | 13.8 | 14.4 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent10_base30` | 10/30 (33%, 95% CI 19–51%) | 6 | 0 | 20 | 13.8 | 14.4 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |
| `recent8` | 12/30 (40%, 95% CI 25–58%) | 7 | 0 | 18 | 13.8 | 14.9 | 5.1–27.8 | 0 (0.00/match) | 0/30 (0%, 95% CI 0–11%) | 0 | yes |

Eligible = control false alarms ≤ 0.10 per match and ≤ 1 early detection.

## Configurations

| Config | min_baseline_ms | min_baseline_buildup | min_recent_buildup | min_half_buildup |
|---|---:|---:|---:|---:|
| `original` | 20 min | 40 | 15 | 6 |
| `recent12` | 20 min | 40 | 12 | 5 |
| `recent10` | 20 min | 40 | 10 | 4 |
| `recent10_base30` | 15 min | 30 | 10 | 4 |
| `recent8` | 20 min | 40 | 8 | 3 |

All statistical thresholds unchanged from Stage 3A (z 2.33 / 1.64, ratio 1.5, half ratio 1.2, 3-tick persistence).

## Insufficient evidence

| Config | All team-ticks | Target team after switch | …baseline length | …baseline build-up | …recent build-up | …5-min half |
|---|---:|---:|---:|---:|---:|---:|
| `original` | 75.7% | 63.6% | 0.0% | 0.0% | 51.5% | 58.3% |
| `recent12` | 66.5% | 48.9% | 0.0% | 0.0% | 32.5% | 47.9% |
| `recent10` | 59.0% | 37.8% | 0.0% | 0.0% | 23.6% | 35.7% |
| `recent10_base30` | 54.3% | 37.8% | 0.0% | 0.0% | 23.6% | 35.7% |
| `recent8` | 51.0% | 23.7% | 0.0% | 0.0% | 12.3% | 22.2% |

Reason columns: share of target-team post-switch ticks naming that shortfall (a tick can name several).

## Opportunity availability

Opponent build-up passes per 10 minutes for the target team, switch to full time (public events). Thirds of the 30 treated matches: low < 14.3 ≤ middle < 17.0 ≤ high.

| Config | Low: correct | Low: median delay | Middle: correct | Middle: median delay | High: correct | High: median delay |
|---|---:|---:|---:|---:|---:|---:|
| `original` | 0/10 | n/a | 3/10 | 17.4 | 7/10 | 13.2 |
| `recent12` | 0/10 | n/a | 3/10 | 16.4 | 7/10 | 13.2 |
| `recent10` | 0/10 | n/a | 3/10 | 14.4 | 7/10 | 13.2 |
| `recent10_base30` | 0/10 | n/a | 3/10 | 14.4 | 7/10 | 13.2 |
| `recent8` | 2/10 | 17.3 | 3/10 | 14.4 | 7/10 | 13.2 |

## Proposed configuration

Selection rule (protocol section 7), applied in order original, recent12, recent10, recent10_base30, recent8: **`recent8`**. This is a proposal for approval; `DEFAULT_CONFIG` is unchanged and the held-out split has not been run.
## Diagnostic: why detections are missed (descriptive; not used for selection)

Target-team assessments in treated development matches whose 10-minute recent window lies entirely after the switch. Produced by a one-off script over the same 30 development pairs; no configuration was added or changed as a result.

| Status / failing condition | `original` | `recent8` |
|---|---:|---:|
| insufficient_evidence | 481 (65.1%) | 180 (24.2%) |
| no_change (primary z ≥ 2.33 and ratio ≥ 1.5 not both met) | 128 (17.3%) | 347 (46.6%) |
| candidate, no corroborating signal | 69 (9.3%) | 111 (14.9%) |
| candidate, all conditions met but persistence 1–2/3 ticks | 32 (4.3%) | 44 (5.9%) |
| candidate, a 5-minute half below 1.2× | 6 (0.8%) | 15 (2.0%) |
| sustained_change | 23 (3.1%) | 47 (6.3%) |
| **Ticks** | 739 | 744 |

Among assessed (not insufficient) ticks, the median pressing rate ratio is 2.53 (`original`) and 2.30 (`recent8`), but the median primary z is only 2.37 and 1.94. The pressing increase is visible in the ratio. In ten-minute windows with few build-up passes, though, the z test lacks the power to reach 2.33. Once minimum-data gates are relaxed, the binding constraints are the primary z threshold and the corroboration requirement, not data availability. Both are outside the scope of this comparison and need the owner's decision.

Notes:
- Switch times here are elapsed match time, which includes first-half stoppage time. So 53'–65' of match time maps to roughly 56–68 elapsed minutes.
- `sustained_change` counts every tick in that state, including those after the first finding.
