# Beyond90 AI

[![CI](https://github.com/ZohaibRahim/Beyond90/actions/workflows/ci.yml/badge.svg)](https://github.com/ZohaibRahim/Beyond90/actions/workflows/ci.yml)

**Football intelligence that proves its insights.** Built for the Microsoft *Inside the Game* Developer Hackathon 2026.

Beyond90 simulates football matches containing **hidden tactical changes**, for example a team abandoning its low block and pressing high. It then tries to detect those changes from the observable match events alone, with no access to the hidden script. Every finding cites the public events and statistics behind it, and the system can answer "insufficient evidence".

All teams, players and matches are fictional and synthetic.

## Why it is different

Most match-analysis demos explain what they already know. Here the analysis side is deliberately kept blind:

- **Information barrier.** The simulator writes `public/` events and a separate `private/` ground truth.
  - Live-side packages (`schemas`, `analytics`, `reporting`, `live`, `detection`) may not import the simulator, the ground truth or the evaluation harness.
  - The live side reads only public files. `tests/test_isolation.py` enforces this.
- **No look-ahead.** Live code reads through an as-of feed that releases each event only once it is fully observable:
  - a pass when the next event starts, so its outcome is known;
  - a pressure when it ends.
  - Analysis up to time T is provably independent of anything after T.
- **Deterministic statistics in code**, unit-tested. Language models never compute numbers.
- **Measured honestly.** The detector was evaluated under a protocol written before any results were seen, with a development/held-out seed split. The held-out split was run exactly once.

## Current status

| Stage | What | Status |
|---|---|---|
| 1 | Versioned public event schema, match setup, football-rule stream validator | Done |
| 2 | Seeded match simulator with hidden pressing interventions; possession and time accounting; public match reports | Done |
| 3A | As-of feed, rolling pressing metrics, deterministic sustained-change detector with auditable evidence | Done |
| 3B | Pre-registered benchmark: development comparison, frozen configuration, single held-out run | Done |
| Next | Microsoft Foundry-powered explanation pipeline grounded in detector findings | Not started |
| Later | React/TypeScript frontend, Azure deployment | Not started |

### Detector results (held-out, 30 treated/control match pairs)

The frozen detector (`recent8_z233`) was evaluated once on seeds it had never seen. The scenario is an away team switching from a low block to a high press between 53' and 65'.

| Measure | Held-out | Development |
|---|---|---|
| Switches detected (recall, 95% CI) | 8/30 (27%, 14–44%) | 12/30 (40%, 25–58%) |
| Detected within 15 minutes | 2/30 | 7/30 |
| Median delay when detected | 22.8 min | 13.8 min |
| Early (pre-switch) detections | 2 | 0 |
| False alarms per no-intervention control match | 0.13 | 0.00 |
| Findings naming the wrong team or direction | 0 | 0 |

The detector is **conservative and usually late**: it misses most switches. A finding is evidence of a sustained pattern, not proof of a tactical decision. These numbers come from synthetic matches with a single type of tactical change, and say nothing about real football. Full details, the comparison with development and the limitations are in [`docs/BENCHMARK_HOLDOUT_RESULTS.md`](docs/BENCHMARK_HOLDOUT_RESULTS.md).

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"

python -m pytest                      # full test suite
```

**Simulate a match and run the detector:**

```bash
# Writes data/generated/<match_id>/{public,private}/ and reports/{public,private}/
python -m beyond90.simulator --seed 42 --control

# The detector reads only <match_id>/public/
python -m beyond90.detection data/generated/m-5cb13f027b84 \
    --out reports/public/detection_seed42.md \
    --evidence reports/public/detection_seed42_evidence.json
```

Seed 42 produces match `m-5cb13f027b84`. The match id is an opaque hash that does not reveal the seed or the hidden script. `--control` also writes the same match with the intervention removed, to `<match_id>-control/`.

**Re-run the development benchmark:**

```bash
python -m beyond90.benchmark --split dev                    # minimum-data comparison
python -m beyond90.benchmark --split dev --experiment 3b1b  # primary-z comparison
```

The held-out split is locked. It needs an explicit unlock and a clean git tree, and refuses to run a second time.

## Repository layout

```
src/beyond90/
  schemas/       public event schema, match setup, stream validator
  analytics/     deterministic box-score, possession and sequence statistics
  reporting/     public match reports
  live/          public-file access and the as-of feed
  detection/     pressing-change detector, rolling metrics, evidence retrieval
  ground_truth/  HIDDEN intervention scripts (simulator and evaluation only)
  simulator/     seeded match engine; writes public and private output separately
  benchmark/     offline evaluation harness (frozen seed split, scoring)
tests/           unit, integration, isolation and no-look-ahead tests
docs/            progress log, evaluation protocol, benchmark results
reports/public/  example public reports for seed 42
```

## Documentation

- [`docs/PROGRESS.md`](docs/PROGRESS.md): stages, decisions, measured statistics, test results, limitations.
- [`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md): scoring rules, seed split, amendments and the frozen-configuration record.
- [`docs/BENCHMARK_DEV_RESULTS.md`](docs/BENCHMARK_DEV_RESULTS.md) and [`docs/BENCHMARK_DEV_RESULTS_3B1B.md`](docs/BENCHMARK_DEV_RESULTS_3B1B.md): development comparisons, including configurations that were not chosen.
- [`docs/BENCHMARK_HOLDOUT_RESULTS.md`](docs/BENCHMARK_HOLDOUT_RESULTS.md): final held-out evaluation.
- [`docs/REALISM_REVIEW.md`](docs/REALISM_REVIEW.md): football-realism facts, reserved for the owner's assessment.
- [`docs/SAMPLE_RUN.log`](docs/SAMPLE_RUN.log): real end-to-end run on seed 42 (tests, simulation, detection, holdout lock).
- [`docs/COMMIT_HASH_MAP.md`](docs/COMMIT_HASH_MAP.md): maps commit hashes cited in the docs to the published history.
- [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md): hackathon brief and vision.
