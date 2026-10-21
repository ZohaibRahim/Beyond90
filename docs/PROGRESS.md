# Beyond90 AI — Progress

Last updated: 2026-10-20. Keep this file current at the end of every stage.

## Completed stages

| Stage | Status | Commit | Summary |
|---|---|---|---|
| 1. Scaffold + schemas | Approved | `0cf2018` | Repo, pytest, CLAUDE.md, event schema v1, hidden intervention schema, isolation test |
| 2. First simulator | Provisionally approved | `4c4bd3c` | Event schema v2, roster/lineup schema, football-rule validator, seeded engine with hidden pressing switch, public/private output |
| 2.5 Corrections | Conditionally approved | `71f1695` | Goalkeeper back-pass mechanism, time-based possession, possession sequences, public/private report split, live public-only file access, paired-control intervention review |
| 2.6 Final checks | Awaiting review | this commit | Mutually exclusive time accounting; fix for pass receptions piling up on the goal line and touchlines; pattern-vs-cause rule |

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

- Stage 2.6: **262 passed** (`.venv/Scripts/python -m pytest`, about 4 s).
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

## Next task

Stage 3 (approved next, not started): deterministic tactical change detection and evaluation using public events only, scored against private ground truth (detection accuracy, false alarms, detection delay). Detectors may read only through `beyond90.live`, and must report pattern changes, never causes of individual goals.
