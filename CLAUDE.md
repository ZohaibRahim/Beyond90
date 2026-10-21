# Beyond90 AI — Development Rules

Hackathon project (Microsoft Inside the Game, deadline 2026-10-27 23:59 PT). See `PROJECT_BRIEF.md` for vision.

## Commands

- Activate env: `.venv/Scripts/activate` (Windows Git Bash) — or call `.venv/Scripts/python` directly.
- Run tests: `.venv/Scripts/python -m pytest`
- Install deps: `.venv/Scripts/python -m pip install -e ".[dev]"` (or install `pydantic` and `pytest` directly; tests use `pythonpath = src`).
- Simulate a match: `PYTHONPATH=src .venv/Scripts/python -m beyond90.simulator --seed 42`
  (public + private output in `data/generated/<match_id>/`, report in `reports/`).

## Layout

```
src/beyond90/
  schemas/events.py        # PUBLIC observable event schema (versioned)
  schemas/match_setup.py   # PUBLIC rosters, line-ups, pitch orientation helpers
  schemas/validation.py    # PUBLIC football-rule stream validator (incremental, no look-ahead)
  analytics/               # Live analysis (deterministic stats). Must never import ground_truth or simulator.
  ground_truth/            # HIDDEN: tactical scripts + applied record. Simulator + evaluation ONLY.
  simulator/               # Seeded match engine; reads ground_truth; writes public/ and private/ separately.
tests/
```

## Hard rules (non-negotiable)

1. **Information barrier.** `beyond90.ground_truth` may be imported only by the simulator and the offline evaluation harness. `beyond90.schemas`, `beyond90.analytics`, and any future agent/API/frontend code must never import it **or `beyond90.simulator`**, and must read only `public/` output. Detectors must infer tactics from events, never from scripts. `tests/test_isolation.py` enforces this; extend its list of guarded packages when adding new live-side packages.
2. **No future events.** Live analysis consumes events strictly in `sequence` order and may only use events with sequence <= current. Events may reference only *earlier* events (`related_event_id`).
3. **Deterministic stats in code.** All statistics (possession, pass completion, pressures, PPDA, etc.) are computed in Python and unit-tested. LLMs never compute numbers.
4. **Grounded explanations.** Every AI claim must cite event IDs and/or verified statistic values. The system must be able to answer "insufficient evidence" and decline.
5. **Synthetic only.** Fictional teams/players. No real clubs, players, or real match data.
6. **Reproducible.** Simulations take an explicit seed; same seed ⇒ identical events. Never use unseeded randomness.
7. **Never fabricate results.** Report only test/evaluation numbers actually produced by running code.

## Schema conventions

- Pydantic v2 models, `extra="forbid"`, `frozen=True`. Unknown fields are rejected — this also blocks hidden metadata leaking into events.
- Every event carries `schema_version`. Breaking changes ⇒ bump the major version and add a new model; don't silently mutate v1.
- Coordinates: **fixed** metres on a 105 x 68 pitch. Ends swap at half-time; derive team-relative coordinates with `MatchSetup.to_attacking_frame` (never store them).
- Time: `period` + `clock_ms` (ms since the period's kickoff). Ordering truth is `sequence`.
- Public events hold observable facts only: no tactical intent, intervention labels, xG or difficulty scores. Computed metrics live in `analytics`, outside event records.
- Possession: open-play turnovers are explicit `possession_change` events; dead balls resume with a `restart`. Every simulated stream must pass `validate_match`.

## Working style

- Prefer simple, tested code over cleverness; scope to what ships by the deadline.
- Add a test with every schema or stats change. Run the full suite before committing.
- Don't commit secrets; Azure/Foundry config goes in `.env` (gitignored).
