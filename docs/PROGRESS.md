# Beyond90 AI — Progress

Last updated: 2026-10-20. Keep this file current at the end of every stage.

## Completed stages

| Stage | Status | Commit | Summary |
|---|---|---|---|
| 1. Scaffold + schemas | Approved | `0cf2018` | Repo, pytest, CLAUDE.md, event schema v1, hidden intervention schema, isolation test |
| 2. First simulator | Provisionally approved | `4c4bd3c` | Event schema v2, roster/lineup schema, football-rule validator, seeded engine with hidden pressing switch, public/private output |
| 2.5 Corrections | Conditionally approved | `71f1695` | Goalkeeper back-pass mechanism, time-based possession, possession sequences, public/private report split, live public-only file access, paired-control intervention review |
| 2.6 Final checks | Stage 3A requested next (no explicit approval recorded) | `cf07bac` | Mutually exclusive time accounting; fix for pass receptions piling up on the goal line and touchlines; pattern-vs-cause rule |
| 3A Detection | Approved, completed | `c112976` | As-of feed with release-time semantics; rolling 5/10-min pressing metrics; deterministic sustained-change detector with insufficient-evidence outcome; structured findings; reconciled time-table display |
| 3B.1 Dev benchmark | Approved, completed | `e7a8588` | Correctness pass (full evidence, interval overlap, z caveats); pre-registered protocol (`a33e74f`); development benchmark of 5 minimum-data configs; holdout locked and not run |
| 3B.1B Final dev comparison | Approved, completed | `8ef0d4a` | n/a display fix; protocol Amendment 1 (`6062b8e`); primary z 2.33 / 2.00 / 1.64 on recent8 gates; recommend freezing `recent8_z233`; holdout not run |
| 3B.2 Held-out evaluation | Freeze committed, held-out run pending | this commit | `recent8_z233` frozen as `DEFAULT_CONFIG`; historical configs pinned; harness evaluates only the frozen config on the holdout (one run, clean tree, commit recorded) |

## Stage 3B part 1B: final bounded development comparison

**Before running:**
- **Protocol Amendment 1** (dated 2026-10-21, committed `6062b8e` before the run) is appended to `docs/EVALUATION_PROTOCOL.md`. It records why recall was insufficient: the primary z lacked power in small windows. It fixes the configurations, the selection rule and the tie-breakers in advance. Sections 1–8 and `docs/BENCHMARK_DEV_RESULTS.md` are unchanged.
- **Defect fixed:** `WindowMetrics` displayed build-up rates only when the denominator was at least a fixed 10, but `recent8` accepts 8. As a result, 1 of 12 `recent8` development findings, and 329 assessed ticks, showed the primary rate as "n/a".
  - Windows now display rates down to the gate the detector applies to that window. Decisions are unchanged (same 12 findings).
  - Tests: a low-data detection displays its evidence, every assessed tick in real matches shows its primary rates, and statements never contain "n/a".
- **Feed boundary re-verified** by a new tick-by-tick test. At every tick the detector holds exactly the events visible at that tick, every one released by then, and none withheld that should be visible.

**Results** (same 30 development pairs; `docs/BENCHMARK_DEV_RESULTS_3B1B.md`):

| Config | Correct | ≤15 min | Median delay | Early | Control FA | Treated non-target FA | Post-switch insufficient | vs `original`: lost / gained |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| original (reference) | 10/30 | 5 | 14.6 | 0 | 0 | 0 | 63.6% | — |
| recent8_z233 | 12/30 | 7 | 13.8 | 0 | 0 | 0 | 23.7% | 0 / 2 |
| recent8_z200 | 13/30 | 7 | 14.4 | 1 | 1 | 0 | 23.7% | 1 / 4 |
| recent8_z164 | 12/30 | 6 | 15.1 | 2 | 4 (ineligible) | 0 | 23.7% | 2 / 4 |

- **Selection** (Amendment 1): `recent8_z233`. `recent8_z200` gains only +1 and loses the false-alarm tie-breaker (1 vs 0); `recent8_z164` is ineligible.
- **Reproducibility:** `original` and `recent8_z233` reproduce the part 1 results exactly.
- **Recommendation to freeze:** `recent8_z233`, i.e. `DetectorConfig(min_recent_buildup=8, min_half_buildup=3)` with everything else at Stage 3A values. Awaiting the owner's approval; `DEFAULT_CONFIG` is unchanged.
- **Unfavourable results** (recorded in the results file):
  - lower z adds early alarms (which also appear in the paired controls) and longer delays;
  - high-opportunity matches drop from 7/10 to 5/10 at z 1.64;
  - recall stays at 43% or less;
  - 16 of 30 switches are detected by no configuration.
- **Last planned threshold experiment.** Further changes need a demonstrated correctness defect.

## Stage 3B part 1: correctness pass and development benchmark

**Correctness pass (before benchmarking):**
- **Full evidence:** `detection.evidence.finding_evidence(setup, events, finding)` replays exactly the events released at detection time. It returns every numerator and denominator event id (pressures, regains, every opponent pass in each pass statistic, controlled-possession intervals) for the baseline, the recent window and both halves. Findings keep only their headline ids. The CLI gains `--evidence`. Tests check that the counts reproduce the finding's metrics, that every evidence event was released by detection time, and that later events change nothing.
- **Controlled-time fix (defect):** a controlled interval used to count its full duration in whichever window held its start time. Intervals are now stored as `[start, end)` and windows count only the overlap. Zero-length intervals are dropped.
  - Tests: boundary unit tests, plus a brute-force comparison against `analytics.possession` with window edges inside intervals.
  - Decisions are unchanged, because the metric is reported but not used to decide. The seed-42 finding is identical.
- **Feed review:** no defect found. A new test checks that every event is released no earlier than its start, a pressure no earlier than its end, and a pass no earlier than the next event.
- **z-score caveats:** documented in `detector.py` and the protocol. They are heuristics, not calibrated probabilities; overlapping windows make consecutive ticks strongly dependent, and multiple testing inflates the chance of a spurious finding.

**Benchmark:** protocol in `docs/EVALUATION_PROTOCOL.md`, committed (`a33e74f`) before any development run. The harness is `beyond90.benchmark`; live packages may not import it, and the holdout is locked. The aggregate report is in `docs/BENCHMARK_DEV_RESULTS.md`; per-match hidden details are in `reports/private/` (gitignored).

**Development results** (30 pairs; statistical thresholds fixed; only minimum-data gates varied):

| Config | Correct | ≤15 min | Early | Median delay | Control FA | Post-switch insufficient |
|---|---:|---:|---:|---:|---:|---:|
| original (15/6) | 10/30 | 5 | 0 | 14.6 min | 0 | 63.6% |
| recent12 (12/5) | 10/30 | 5 | 0 | 14.3 min | 0 | 48.9% |
| recent10 (10/4) | 10/30 | 6 | 0 | 13.8 min | 0 | 37.8% |
| recent10_base30 | 10/30 | 6 | 0 | 13.8 min | 0 | 37.8% |
| recent8 (8/3) | 12/30 | 7 | 0 | 13.8 min | 0 | 23.7% |

- **Selection:** the pre-registered rule proposes `recent8`, which gets 2 more correct detections with zero control false alarms. It is not adopted: `DEFAULT_CONFIG` is unchanged pending the owner's approval.
- **Opportunity:** no configuration detects anything in the low-opportunity third (fewer than 14.3 opponent build-up passes per 10 minutes) except `recent8` (2/10). The high-opportunity third gets 7/10 under every configuration.
- **Diagnostic:** after relaxing the minimum-data gates, most post-switch ticks fail the primary z test (median ratio 2.3×, median z 1.94) or lack corroboration. Further recall gains would need a change to the statistical thresholds or the method, which is a decision for the owner.

## Stage 3A: deterministic pressing-change detection

**Observability (`beyond90.live.feed`).** Event timestamps mark when an action started. Release rules:
- A **pass** is released when the next event starts. Its outcome, end location and recipient are not known before; a pass with no following event is never released.
- A **pressure** is released at `clock_ms + duration_ms`.
- **Everything else** is released at its own timestamp.
- **Order:** releases are monotone in sequence order, so the visible set at time T is a prefix of the stream and contains only events that started by T.

No schema change.

**Rolling metrics (`beyond90.detection.metrics`).** 5- and 10-minute windows (and baseline) per team, treating that team as the potential presser:
- attacking-third pressures (x ≥ 70 in the presser's frame);
- high regains;
- opposition build-up passes (from x < 35 in the opposition's own frame) and their completion;
- opposition long-pass share (≥ 30 m);
- opposition keeper passes and long share (≥ 35 m);
- opposition controlled possession minutes.

Pressures are normalised per opposition build-up pass (primary) and per opposition controlled minute (reported). Rates below minimum denominators are `None`.

**Detector (`beyond90.detection.detector`).** Evaluated every whole minute against the team's own earlier baseline. Thresholds were fixed before any run and not tuned:
- **Data:** baseline ≥ 20 min with ≥ 40 opposition build-up passes; recent ≥ 15, with ≥ 6 in each 5-min half. Otherwise `insufficient_evidence`.
- **Primary:** high pressures per build-up pass, conditional binomial |z| ≥ 2.33 and ratio ≥ 1.5 (or ≤ 1/1.5).
- **Not a spike:** both 5-minute halves move in the same direction by ≥ 1.2×.
- **Corroboration:** ≥ 1 of high regains, opposition defensive-third completion (opposite direction) or opposition long-pass share, with z ≥ 1.64.
- **Persistence:** 3 consecutive ticks → `sustained_change`; otherwise `candidate` or `no_change`.

Findings carry team, direction, detection time, evidence window, metrics, supporting public event ids (high pressures and high regains in the window), and an association-only statement.

**Seed 42 results** (`reports/public/detection_seed42.md`, `..._control.md`). Thresholds unchanged after viewing:
- **Scripted match:** one finding, Kestrel Bay pressing increase at 74' (P2 29:00). Primary z = 3.41, ratio 4.91; corroborated by NBH defensive-third completion (85% → 65%, z = −1.92).
- **Ground truth** (read only afterwards, for this report): the switch first affected events at 59.6', so the delay was 14.4 min. Most of it was `insufficient_evidence`: NBH made fewer than 15 build-up passes per 10 minutes for much of 60'–71'.
- **Paired control:** no findings, so no false alarm in this pair.
- **Spike rejection:** a 51' candidate (ratio 6.0) appears identically in both runs, before the switch. It stayed a candidate, which is the intended spike rejection.
- **Coverage gap:** Kestrel Bay is `insufficient_evidence` for all of period 1 in both runs.

**Time table rounding.** Rows were truncated to whole seconds independently (30:14 + 26:19 + 5:46 + 34:06 = 96:25 ≠ 96:27). Displayed seconds and tenths of a percent now use largest-remainder rounding to the displayed total. Underlying milliseconds are unchanged.

## Stage 2.6 findings

**Time accounting.** The old figures already summed (ball in play + dead = elapsed), but "contested" was a *subset* of ball in play and was listed as if it were a third category. There was also a real misclassification: when a loose ball (after a parried, blocked or woodwork shot) was followed by a restart, the whole 20–35 s stoppage was counted as contested, because no public event marks the ball leaving play. Fix:
- Every interval now belongs to exactly one category: controlled (per team), contested in play, or stoppage.
- A loose ball followed by a restart or substitution is a stoppage.
- The categories reconcile exactly with elapsed time (tested).

The reclassification alone moves 3.3 min per match from contested to stoppage. The engine was not changed for this.

**Goal-line passes.** Confirmed defect in target selection plus clamping:
- **Forward room:** final-third pass targets kept a forward mean (+1 m, sd 9 m) whatever the distance to the goal line.
- **Clamping:** overshooting targets were clamped to x = 104, carries to x = 103.5, and lateral targets to y = 1 / y = 67.
- **Result:** over 20 seeds, 597 of 15,713 completed passes (3.8%) ended at exactly x = 104.0. 7.1% ended at x ≥ 98, runs of up to 8 consecutive receptions sat on the goal line, and about 520 receptions sat on each touchline clamp.

Fix:
- **Reflection:** overshooting targets are reflected back inside the receivable area instead of clamped.
- **Ball out over the goal line:** a pass goes out there only when its intended target is beyond the line.
- **Cut-backs:** final-third passes lose forward room near the goal line and are pulled toward the centre of the box.

After the fix: 0 receptions at the old clamp lines, 2.5% at x ≥ 98, and the longest goal-line run is 3. A regression test over 10 seeds checks this; it fails on the old engine and passes on the new one.

The artifact had inflated scoring by creating point-blank positions. Goals per match fell from 2.8 to 1.9. Shot conversion was **not** retuned to win them back; this is listed as a realism question.

**Pattern vs cause.** Seed 42's goals are not attributed to the press anywhere. Private evaluation outputs state that paired-control differences are aggregate patterns, not causes of individual goals. CLAUDE.md rule 4 now requires future explanations to separate pattern changes from causal claims about single goals.

## Architectural decisions

- **Information barrier.** Live-side packages (`schemas`, `analytics`, `reporting`, `live`) never import `ground_truth` or `simulator`. Enforced by AST and text checks in `tests/test_isolation.py`, verified with planted-leak probes.
- **Public/private split on disk.** The simulator writes `data/generated/<match_id>/public/` and `.../private/` separately. The live runtime reads files only through `beyond90.live.load_public_match`, which refuses any path that resolves outside `public/` or passes through a `private` directory.
- **Reports.** `reports/public/` holds reports built only from public setup + events (`beyond90.reporting`). `reports/private/` (gitignored) holds evaluation records with hidden ground truth (`beyond90.simulator.evaluation`).
- **Opaque match ids.** Match ids are hashes and never reveal the seed. The public report omits the seed, since the seed plus the simulator would reproduce the hidden script.
- **Fixed coordinates.** Events use fixed 105 x 68 m coordinates. Team-relative frames are derived (`MatchSetup.to_attacking_frame`) and account for the halftime switch.
- **Observable facts only in events.** No xG, difficulty, intent or tactical labels. Statistics are computed in `beyond90.analytics`.
- **Explicit possession.** Open-play turnovers are `possession_change` events; dead balls resume with `restart`. Every simulated stream must pass `validate_match`, which is incremental with no look-ahead.
- **Time accounting.** Controlled (per team) + contested + stoppage = elapsed, with no overlaps. Possession share = a team's share of controlled time. An interval's category is final once the next event arrives. Pass share is reported separately and labelled as not possession.
- **Schema versioning.** Breaking change ⇒ bump the major version and add a new model. The v1→v2 event change replaced v1 in place before any consumer existed; this was a one-off. No schema changed in Stages 2.5–2.6.
- **Intervention modelling.** Hidden settings only shift probabilities: press likelihood by zone, pass-completion penalty, back-pass likelihood when pressed, and keeper distribution when pressed. Scripted and control matches with the same seed are event-for-event identical until the intervention.
- **Positive-control scenario.** The away team switches from a low block to a high press at a seed-drawn time between 53' and 65'. It is deliberately easy to detect and kept at full strength.
- **Explanations.** Pattern changes ≠ causes of individual goals (CLAUDE.md rule 4).

## Test results

- Stage 3B part 1B: **331 passed** (about 6 s) (`.venv/Scripts/python -m pytest`). New tests: low-data detection displays its evidence (no n/a); assessed ticks always show primary rates (3 configs × 2 seeds × treated/control); tick-by-tick feed boundary; Amendment 1 candidate set, selection rule with tie-breakers, per-seed worsening.
- Stage 3B part 1: **318 passed** (about 7 s) (`.venv/Scripts/python -m pytest`). New tests:
  - interval-overlap boundaries and brute-force controlled time;
  - full-evidence counts match the finding's metrics, all evidence was released by detection time, and later events have no effect;
  - feed release ordering;
  - split frozen, disjoint and excluding seeds 42 and 0–29; holdout locked;
  - candidate configs vary only the data gates;
  - the selection rule and Wilson interval;
  - seed-42 scoring reproduces the 14.4-minute delay.
- Stage 3A: 302 passed (`.venv/Scripts/python -m pytest`, about 8 s). New tests cover:
  - the as-of feed and the rolling metrics;
  - detector logic with scripted windows (persistence, spike, uncorroborated, sparse, too early, decrease);
  - cutoff equals event-prefix analysis, a different future changes nothing, and the hidden script has no influence before the switch;
  - supporting ids are released before detection, and finding wording is association-only;
  - time-table reconciliation.
- Leak probe: a planted simulator import in `detection` was caught.
- Stage 2.6: 262 passed.
- The spatial-concentration regression test was run against the pre-fix engine and failed as expected (7.0% of receptions at x ≥ 98).
- Leak probes: planted imports of hidden modules in `analytics` (Stage 2) and `reporting` (Stage 2.5) were caught by the isolation tests, then removed.

## Simulator statistics (seeds 0–19, per team unless noted, after Stage 2.6)

| Metric | Mean | Range |
|---|---:|---|
| Goals per match | 1.9 | was 2.8, inflated by the goal-line artifact |
| Shots / on target | 11.2 / 4.0 | 4–17 shots |
| Passes (completion) | 518 (78.2%) | 462–583 |
| Pressures / in attacking third | 142 / 31 | 118–159 |
| Tackles (won) | 15.4 (9.3) | |
| Interceptions | 14.3 | |
| Fouls | 10.4 | 4–16 |
| Corners / throw-ins / goal kicks | 5.9 / 19.6 / 5.0 | |
| Substitutions | 4.3 | 3–5 |
| Passes received by goalkeepers (per match, both teams) | 15.6 | was 2.1 before Stage 2.5 |
| Completed passes ending x ≥ 98 m (team frame) | 2.5% | was 7.1% |
| Ball in play (per match) | 61.4 min | 57.8–64.8 |
| Stoppages / contested (per match) | 33.7 / 5.75 min | |
| Possession sequences (per match) / mean passes | 261 / 3.98 | |

Pressing-intervention review (30 seeds, scripted vs paired control, after the switch; full table in `reports/private/intervention_review.md`, regenerate with `--review 30`). These are aggregate pattern differences, not causes of individual goals.

| Metric | Scripted | Control | Seeds scripted > control |
|---|---:|---:|---:|
| Pressing team attacking-third pressures / min | 0.629 | 0.187 | 30/30 |
| Pressing team attacking-third turnovers won / min | 0.191 | 0.106 | 28/30 |
| Pressing team fouls / min | 0.111 | 0.109 | 15/30 |
| Pressed team pass completion | 75.9% | 79.2% | 9/30 |
| Pressed team completion from own third | 76.2% | 82.1% | 8/30 |
| Pressed team long-pass share (≥30 m) | 10.9% | 8.8% | 21/30 |
| Pressed team passes to own keeper / min | 0.097 | 0.064 | 20/30 |
| Pressed team keeper long share (≥35 m) | 50.9% | 34.4% | 18/28 |
| Pressed team passes per sequence | 3.61 | 4.23 | 9/30 |
| Pressed team possession share | 48.1% | 51.4% | 6/30 |
| Shots / min: pressing team | 0.131 | 0.081 | 23/30 |
| Shots / min: pressed team | 0.095 | 0.108 | 15/30 |

## Current limitations

Unsupported match mechanics (also listed in every public report):

- Penalties, cards, injuries, own goals, drop balls, advantage, extra time and shoot-outs.
- Fouls never occur inside the penalty area.
- No off-ball positions, dribbles or carry events; carries are implicit gaps between pass end and next action.
- Goalkeepers act only near their own goal.
- Substitutions only in the second half (including at half-time), like-for-like where possible.
- Shot quality is internal (distance and body part only).

Measurement limitations:

- Time accounting depends on event timestamps. A completed pass in flight is credited to the passer. The moment a loose ball leaves play is not observed (the whole interval counts as a stoppage).
- Formation is reported as position counts from the team sheet ("4-3-3"), not inferred from play.
- Only the pressing intervention is simulated; `tempo_change` and `defensive_line_change` exist in the schema but the engine rejects them.

Outstanding realism questions are listed in `docs/REALISM_REVIEW.md` for the user's review.

Detection limitations (Stage 3A):

- Evaluated on one scripted/control pair only; no accuracy or false-alarm rate is claimed yet.
- Fixed minimum denominators leave long `insufficient_evidence` stretches when the opponent builds up rarely (KES all of period 1 in seed 42).
- One finding per team per direction, with no re-baselining after a detection. Ticks every whole minute. The baseline is the whole earlier match, so an earlier change would dilute it.
- Multiple comparisons (about 70 ticks × 2 teams × 2 directions) are not corrected beyond persistence and corroboration.

## Next task

Awaiting the owner's approval to freeze `recent8_z233`. Once frozen, and only on the owner's instruction, run the locked held-out split once with that configuration and report the results as they come out. Not started: AI agents, frontend, Azure.

The holdout harness currently compares the part 1 candidate set. Before the holdout run it must be pointed at the single frozen configuration. That is a small harness change, to be made and reviewed alongside the freeze.
