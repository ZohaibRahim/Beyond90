# Beyond90 AI — Development Rules

Hackathon project (Microsoft Inside the Game, deadline 2026-10-27 23:59 PT). See `PROJECT_BRIEF.md` for vision.

## Commands

- Activate env: `.venv/Scripts/activate` (Windows Git Bash) — or call `.venv/Scripts/python` directly.
- Run tests: `.venv/Scripts/python -m pytest`
- Install deps: `.venv/Scripts/python -m pip install -e ".[dev]"` (or install `pydantic` and `pytest` directly; tests use `pythonpath = src`).
- Detect: `PYTHONPATH=src .venv/Scripts/python -m beyond90.detection data/generated/<match_id> --out reports/public/detection.md`
- Simulate a match: `PYTHONPATH=src .venv/Scripts/python -m beyond90.simulator --seed 42 [--review 30] [--control]`
  (data in `data/generated/<match_id>/{public,private}/`; public report in `reports/public/`;
  private evaluation record and intervention review in `reports/private/`, gitignored).

## Layout

```
src/beyond90/
  schemas/events.py        # PUBLIC observable event schema (versioned)
  schemas/match_setup.py   # PUBLIC rosters, line-ups, pitch orientation helpers
  schemas/validation.py    # PUBLIC football-rule stream validator (incremental, no look-ahead)
  analytics/               # Live analysis (deterministic stats, possession, sequences). Public data only.
  reporting/               # Public human-facing reports from public setup + events only.
  live/                    # Live runtime: public/ file access (refuses private paths) and the as-of feed.
  detection/               # Deterministic pressing-change detector (public events via live.feed only).
  ground_truth/            # HIDDEN: tactical scripts + applied record. Simulator + evaluation ONLY.
  simulator/               # Seeded match engine; reads ground_truth; writes public/ and private/ separately;
                           # evaluation.py renders PRIVATE records.
tests/
docs/PROGRESS.md           # Stages, decisions, test results, limitations, next task. Update every stage.
docs/REALISM_REVIEW.md     # Owner's football judgments. Never fill in assessments on the owner's behalf.
```

## Hard rules (non-negotiable)

1. **Information barrier.** `beyond90.ground_truth` may be imported only by the simulator and the offline evaluation harness. `beyond90.schemas`, `beyond90.analytics`, and any future agent/API/frontend code must never import it **or `beyond90.simulator`**, and must read only `public/` output. Detectors must infer tactics from events, never from scripts. `tests/test_isolation.py` enforces this; extend its list of guarded packages when adding new live-side packages.
2. **No future events.** Live analysis consumes events strictly in `sequence` order and may only use events with sequence <= current. Events may reference only *earlier* events (`related_event_id`). Event timestamps mark when an action STARTED; live code must read through `beyond90.live.feed.AsOfFeed`, which releases a pass only when the next event starts (outcome known) and a pressure only at `clock_ms + duration_ms`.
3. **Deterministic stats in code.** All statistics (possession, pass completion, pressures, PPDA, etc.) are computed in Python and unit-tested. LLMs never compute numbers.
4. **Grounded explanations.** Every AI claim must cite event IDs and/or verified statistic values. The system must be able to answer "insufficient evidence" and decline. Distinguish **pattern changes** (e.g. "attacking-third pressures rose from X to Y per 15 min") from **causal claims about individual goals or chances**. Never attribute a specific goal to a tactical change unless that goal's own event sequence supports it (e.g. a turnover won high up directly before it); a goal built from deep is not evidence for a high press.
5. **Synthetic only.** Fictional teams/players. No real clubs, players, or real match data.
6. **Reproducible.** Simulations take an explicit seed; same seed ⇒ identical events. Never use unseeded randomness.
7. **Never fabricate results.** Report only test/evaluation numbers actually produced by running code.

## Schema conventions

- Pydantic v2 models, `extra="forbid"`, `frozen=True`. Unknown fields are rejected — this also blocks hidden metadata leaking into events.
- Every event carries `schema_version`. Breaking changes ⇒ bump the major version and add a new model; don't silently mutate an existing version. (The v1→v2 in-place replacement happened before any consumer existed and is not a precedent.)
- Coordinates: **fixed** metres on a 105 x 68 pitch. Ends swap at half-time; derive team-relative coordinates with `MatchSetup.to_attacking_frame` (never store them).
- Time: `period` + `clock_ms` (ms since the period's kickoff). Ordering truth is `sequence`.
- Public events hold observable facts only: no tactical intent, intervention labels, xG or difficulty scores. Computed metrics live in `analytics`, outside event records.
- Possession: open-play turnovers are explicit `possession_change` events; dead balls resume with a `restart`. Every simulated stream must pass `validate_match`.

## Working style

- Prefer simple, tested code over cleverness; scope to what ships by the deadline.
- Add a test with every schema or stats change. Run the full suite before committing.
- Calibrate simulator behaviour through mechanisms with a football rationale, never by tuning counts to a target.
- Detector thresholds are fixed in `DetectorConfig` before evaluation runs. Never tune them against hidden ground truth; justify changes from public data or prior reasoning, choose them on development seeds, and evaluate on held-out scenarios (Stage 3B).
- Update `docs/PROGRESS.md` at the end of each stage.
- Don't commit secrets; Azure/Foundry config goes in `.env` (gitignored).
