# Commit hash map

On 2026-10-21, before the first push, commit messages were rewritten to remove a trailer line. Author, date and file contents of every commit are unchanged: each rewritten commit has the same tree hash as the original. Hashes cited in `docs/` (e.g. the evaluated commit `762db64` in `BENCHMARK_HOLDOUT_RESULTS.md`) refer to the original hashes below.

| Original | Rewritten | Tree (unchanged) | Subject |
|---|---|---|---|
| `cdea228` | `f1dacf8` | `1af297a` | Record Stage 3B part 2 commit hash |
| `1a0c656` | `b0a6de5` | `aa6f59f` | Stage 3B part 2: final held-out evaluation results |
| `762db64` | `05df214` | `0b9ab7a` | Stage 3B part 2 freeze: recent8_z233 as DEFAULT_CONFIG; holdout-only harness |
| `0578669` | `f2d9be4` | `468c959` | Record Stage 3B part 1B commit hash |
| `8ef0d4a` | `85f3af8` | `557e755` | Stage 3B part 1B: final bounded primary-z comparison on dev seeds |
| `6062b8e` | `98e8fda` | `8f8a626` | Stage 3B part 1B pre-registration: protocol Amendment 1, n/a display fix |
| `af17ae1` | `f34c300` | `897c27c` | Record Stage 3B part 1 commit hash |
| `e7a8588` | `8b17dae` | `5b13e6d` | Stage 3B part 1: development benchmark results |
| `a33e74f` | `2b3183a` | `0e5aca2` | Stage 3B part 1 pre-registration: evidence audit, interval fix, protocol, harness |
| `df82750` | `d6814a1` | `e90975d` | Record Stage 3A commit hash |
| `c112976` | `1bc7f03` | `5ca92fd` | Stage 3A: as-of feed, rolling pressing metrics, deterministic change detector |
| `d2e1011` | `904a81d` | `0450a00` | Record Stage 2.6 commit hash in progress log |
| `cf07bac` | `687620f` | `c36628c` | Stage 2.6: exclusive time accounting, fix goal-line pass pile-up |
| `9218f32` | `503dbe4` | `b1efac6` | Record Stage 2.1 commit hash in progress log |
| `71f1695` | `1596d23` | `cdc653d` | Stage 2.1: keeper back passes, time-based possession, public/private reports |
| `4c4bd3c` | `7c55285` | `b8c1b96` | Add seeded match simulator with hidden pressing intervention |
| `0cf2018` | `77b766f` | `fa974cc` | Initial project scaffold with v1 event and hidden intervention schemas |
