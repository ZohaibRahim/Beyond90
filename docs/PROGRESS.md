# Beyond90 AI — Progress

Last updated: 2026-10-20. Keep this file current at the end of every stage.

## Completed stages

| Stage | Status | Commit | Summary |
|---|---|---|---|
| 1. Scaffold + schemas | Approved | `0cf2018` | Repo, pytest, CLAUDE.md, event schema v1, hidden intervention schema, isolation test |
| 2. First simulator | Provisionally approved | `4c4bd3c` | Event schema v2, roster/lineup schema, football-rule validator, seeded engine with hidden pressing switch, public/private output |
| 2.1 Corrections | Awaiting review | this commit | Goalkeeper back-pass mechanism, time-based possession, possession sequences, public/private report split, live public-only file access, paired-control intervention review |

## Architectural decisions

- **Information barrier.** Live-side packages (`schemas`, `analytics`, `reporting`, `live`) never import `ground_truth` or `simulator`. Enforced by AST and text checks in `tests/test_isolation.py`, verified with planted-leak probes.
- **Public/private split on disk.** The simulator writes `data/generated/<match_id>/public/` and `.../private/` separately. The live runtime reads files only through `beyond90.live.load_public_match`, which refuses any path that resolves outside `public/` or passes through a `private` directory.
- **Reports.** `reports/public/` holds reports built only from public setup + events (`beyond90.reporting`). `reports/private/` (gitignored) holds evaluation records with hidden ground truth (`beyond90.simulator.evaluation`).
- **Opaque match ids.** Match ids are hashes and never reveal the seed. The public report omits the seed, since the seed plus the simulator would reproduce the hidden script.
- **Fixed coordinates.** Events use fixed 105 x 68 m coordinates. Team-relative frames are derived (`MatchSetup.to_attacking_frame`) and account for the halftime switch.
- **Observable facts only in events.** No xG, difficulty, intent or tactical labels. Statistics are computed in `beyond90.analytics`.
- **Explicit possession.** Open-play turnovers are `possession_change` events; dead balls resume with `restart`. Every simulated stream must pass `validate_match`, which is incremental with no look-ahead.
- **Possession metric.** A time-based estimate: time between consecutive events is credited to the team in possession while the ball is in play, and dead or contested time is excluded. Pass share is reported separately and labelled as not possession.
- **Schema versioning.** Breaking change ⇒ bump the major version and add a new model. The v1→v2 event change replaced v1 in place before any consumer existed; this was a one-off, and the rule applies from now on. No schema changed in Stage 2.1.
- **Intervention modelling.** Hidden settings only shift probabilities: press likelihood by zone, pass-completion penalty, back-pass likelihood when pressed, and keeper distribution when pressed. Scripted and control matches with the same seed are event-for-event identical until the intervention.
- **Positive-control scenario.** The away team switches from a low block to a high press at a seed-drawn time between 53' and 65'. It is deliberately easy to detect (about 3× attacking-third pressures) and kept as a sanity check before harder scenarios.

## Test results

- Stage 2.1: **259 passed** (`.venv/Scripts/python -m pytest`, about 4 s).
- Leak probes: planted imports of hidden modules in `analytics` (Stage 2) and `reporting` (Stage 2.1) were caught by the isolation tests, then removed.

## Simulator statistics (seeds 0–19, per team unless noted, simulator 0.1.0)

| Metric | Mean | Range |
|---|---:|---|
| Goals per match | 2.8 | — |
| Shots / on target | 11.6 / 4.9 | 7–20 shots |
| Passes (completion) | 503 (78.1%) | 432–601 |
| Pressures / in attacking third | 136 / 31 | 107–170 |
| Tackles (won) | 14.3 (8.7) | |
| Interceptions | 15.4 | |
| Fouls | 10.1 | 5–18 |
| Corners / throw-ins / goal kicks | 6.8 / 17.5 / 5.5 | |
| Substitutions | 4.3 | 3–5 |
| Passes received by goalkeepers (per match, both teams) | 14.3 | was 2.1 before the back-pass fix |
| Ball in play (per match) | 63.0 min | 55.7–69.8 |
| Possession sequences (per match) / mean passes | 255 / 3.95 | |

Pressing-intervention review (30 seeds, scripted vs paired control, after the switch; full table in `reports/private/intervention_review.md`, regenerate with `--review 30`):

| Metric | Scripted | Control |
|---|---:|---:|
| Pressing team attacking-third pressures / min | 0.618 | 0.200 |
| Pressing team attacking-third turnovers won / min | 0.211 | 0.132 |
| Pressing team fouls / min | 0.099 | 0.099 |
| Pressed team pass completion | 74.9% | 79.4% |
| Pressed team completion from own third | 73.9% | 80.9% |
| Pressed team long-pass share (≥30 m) | 11.2% | 9.6% |
| Pressed team passes to own keeper / min | 0.101 | 0.058 |
| Pressed team keeper long share (≥35 m) | 54.9% | 37.1% |
| Pressed team passes per sequence | 3.47 | 4.17 |
| Pressed team possession share | 47.5% | 51.8% |
| Shots / min: pressing team, pressed team | 0.138, 0.107 | 0.093, 0.143 |

## Current limitations

Unsupported match mechanics (also listed in every public report):

- Penalties, cards, injuries, own goals, drop balls, advantage, extra time and shoot-outs.
- Fouls never occur inside the penalty area.
- No off-ball positions, dribbles or carry events; carries are implicit gaps between pass end and next action.
- Goalkeepers act only near their own goal.
- Substitutions only in the second half (including at half-time), like-for-like where possible.
- Shot quality is internal (distance and body part only).

Measurement limitations:

- Possession time depends on event timestamps. A pass in flight is credited to the passer; the flight of an incomplete pass counts as "contested" (about 7–9 min per match).
- Formation is reported as position counts from the team sheet ("4-3-3"), not inferred from play.
- Only the pressing intervention is simulated; `tempo_change` and `defensive_line_change` exist in the schema but the engine rejects them.

Outstanding realism questions are listed in `docs/REALISM_REVIEW.md` for the user's review.

## Next task

Awaiting the user's realism review of `reports/public/match_report_seed42.md` and answers in `docs/REALISM_REVIEW.md`. After approval, Stage 3 (not started): tactical change detection from public events only, evaluated against private ground truth (detection accuracy, false alarms, delay).
