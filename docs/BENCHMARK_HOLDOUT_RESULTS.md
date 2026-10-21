# Detector benchmark — final held-out evaluation

Frozen configuration `recent8_z233`, evaluated once on the 30 held-out seed pairs. Harness commit `762db64`; protocol: docs/EVALUATION_PROTOCOL.md sections 1–8 + Amendment 1 + frozen-configuration record. Scoring rules: `docs/EVALUATION_PROTOCOL.md` section 4, unchanged.

Configuration: min_baseline_ms 20 min, min_baseline_buildup 40, min_recent_buildup 8, min_half_buildup 3, z_primary 2.33, z_support 1.64, min_rate_ratio 1.5, min_half_ratio 1.2, persistence 3 ticks, windows 10/5 min.

## Results

| Measure | Development (30 pairs) | Held-out (30 pairs) |
|---|---|---|
| Correct detections (recall, 95% Wilson CI) | 12/30 (40%, 95% CI 25–58%) | 8/30 (27%, 95% CI 14–44%) |
| Correct within 15 minutes | 7/30 | 2/30 |
| Missed | 18/30 | 20/30 |
| Early detections | 0/30 | 2/30 |
| Median delay, correct detections (min) | 13.8 | 22.8 |
| Mean delay (min) | 14.9 | 23.0 |
| Delay range (min) | 5.1–27.8 | 8.6–35.8 |
| Control false alarms (per control match) | 0 (0.00) | 4 (0.13) |
| Control matches with ≥1 false alarm | 0/30 (0%, 95% CI 0–11%) | 4/30 (13%, 95% CI 5–30%) |
| Treated non-target false alarms | 0 | 0 |
| Insufficient evidence, all team-ticks | 51.0% | 51.1% |
| Insufficient evidence, target team after switch | 23.7% | 20.5% |
| …naming recent build-up shortfall | 12.3% | 8.4% |
| …naming a 5-minute-half shortfall | 22.2% | 19.2% |
| …naming baseline shortfalls | 0.0% | 0.0% |

Development figures: the same frozen configuration re-run on the development seeds in the same invocation (must equal `recent8_z233` in `docs/BENCHMARK_DEV_RESULTS_3B1B.md`).

## Breakdown by opponent build-up opportunities

Opponent build-up passes per 10 minutes for the target team, switch to full time (public events). Band edges fixed from the development data (protocol section 5): low < 14.3 ≤ middle < 17.0 ≤ high.

| Band | Dev correct | Dev median delay | Held-out correct | Held-out median delay |
|---|---:|---:|---:|---:|
| low | 2/10 | 17.3 | 2/10 | 30.9 |
| middle | 3/10 | 14.4 | 5/15 | 18.2 |
| high | 7/10 | 13.2 | 1/5 | 31.8 |

The development column was reproduced in the same invocation and matches `recent8_z233` in `docs/BENCHMARK_DEV_RESULTS_3B1B.md` exactly.

## Comparison with development

The detector generalised worse than its development figures suggested, on every headline measure:

| | Development | Held-out | Change |
|---|---|---|---|
| Recall | 40% (12/30) | 27% (8/30) | −4 detections. Intervals overlap (25–58% vs 14–44%), so the drop is consistent with chance and with optimistic selection; it is not proof that performance differs. |
| Detected within 15 min | 7 | 2 | Most held-out detections are late. |
| Median delay | 13.8 min | 22.8 min | Five of eight correct detections came 19.8–35.8 minutes after the switch. |
| Early detections | 0 | 2 | Both are pre-switch false alarms. They also fire in the paired control (the streams are identical before the switch), 17 and 20 minutes before the switch. |
| Control false alarms | 0 in 30 | 4 in 4 of 30 matches (0.13 per match) | **Exceeds the 0.10-per-match limit** the development rule required for eligibility. Under the development criteria this configuration would not have been eligible. |
| Treated non-target false alarms | 0 | 0 | None. The home team (constant medium press) never produced a finding. |
| Insufficient evidence after the switch | 23.7% | 20.5% | Similar. Data availability is not what got worse. |

**Opportunity bands** use edges fixed from the development data:
- **Middle band (15 held-out matches):** 5/15 correct, comparable to development (3/10).
- **High band:** only 1/5 correct, against 7/10 in development. This rests on five matches.
- **Low band:** 2/10 in both splits, but all held-out low-band detections came after 25 minutes.

**Why development was optimistic.** `recent8_z233` was chosen from seven distinct configurations evaluated on the development seeds: five in part 1, and two further z values in part 1B (`recent8_z233` is part 1's `recent8`). The winner's development score is biased upward (selection optimism). The development split also happened to have zero false alarms at this setting, which made the 0.10 limit look comfortably met. The held-out result is the unbiased estimate.

**Frozen configuration unchanged.** Per protocol, the detector, configuration, simulator, scenarios, split and scoring were not modified after these results. No alternative configuration was run on the held-out seeds.

## What has been demonstrated

- An end-to-end, leakage-tested pipeline. A detector that reads only public events, through an as-of feed that never exposes unresolved outcomes, produced findings that were scored offline against hidden ground truth under rules fixed in advance. The development/held-out separation held: a single locked run, on the recorded commit `762db64`.
- On held-out simulated matches, the detector flags the away team's switch from low block to high press in **27% of matches** (95% CI 14–44%). It does so with **0.13 false alarms per control match** (95% CI for matches affected: 5–30%) and a median delay of 23 minutes when it does detect.
- When it fires on a treated match, it fires for the right team in the right direction. Every finding in a treated match was the target team's increase; there were no wrong-team or wrong-direction findings.
- Every finding carries auditable evidence: complete numerator and denominator event ids, all released before the detection time.

## What has not been demonstrated

- **Usable live detection.** Recall is low and detection is usually late. As a live alert, the detector would miss most switches, and would often flag the ones it catches only in the last 20–30 minutes.
- **Reliability of a single finding.** With 4 false alarms against 8 correct detections over 60 matches, a positive finding is meaningful but not trustworthy on its own. Its supporting evidence must be shown, and "insufficient evidence" or "no sustained change" must remain the common answer.
- **Generalisation beyond this scenario.** Every treated match contains the same change: away team, LOW→HIGH, in the second half, at a fixed intervention strength. Not tested:
  - decreases;
  - home-team changes or first-half changes;
  - other tactics (defensive line, tempo);
  - multiple changes in one match;
  - other teams or simulator versions.
- **Real football.** All data are synthetic, from one simulator calibrated for plausibility, not against real event data. The size of the pressing effect, and therefore detectability, is set by the simulator.
- **Calibrated probabilities.** z values are heuristics, and consecutive minute assessments are strongly dependent; the empirical rates above are the only valid error measure. 30 pairs per split gives wide intervals.

## Implications for the next stage (no detector change)

The AI explanation layer must treat a finding as "an observed sustained association, with evidence", never as a confirmed tactical change. It should state that the detector is conservative and often late. When there is no finding, it should say "no sustained change detected" or "insufficient evidence", not "no change happened". And it should cite the event ids and statistics returned by `finding_evidence`.
