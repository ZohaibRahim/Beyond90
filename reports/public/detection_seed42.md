# Pressing-change detection — seed 42

Match `m-5cb13f027b84`: Northbridge Harriers vs Kestrel Bay. Evaluated every minute using only events fully observable at that minute (public data only).

Findings describe associations between observed event rates. They do not explain why play changed and do not attribute any individual pass, turnover or goal to a tactical change.

## Findings

### KES: increase detected at 74' (period 2, 1740s)

Observed increase in Kestrel Bay's attacking-third pressing: pressures per Northbridge Harriers build-up pass went from 0.10 (7/73, earlier in the match) to 0.47 (8/17, last 10 minutes). Over the same period Northbridge Harriers' defensive-third pass completion was 85% -> 65% and Kestrel Bay won the ball in its attacking third 2 times. This is an association between observed event rates; it does not establish why it happened or that it caused any individual pass, turnover or goal.

- Status: sustained_change
- Primary z = 3.41, rate ratio = 4.91, 5-minute halves = 0.56 / 0.38
- Support z: high regains -0.06, opp defensive-third completion -1.92, opp long-pass share 0.20
- Supporting public event ids (10): `m-5cb13f027b84-01229`, `m-5cb13f027b84-01236`, `m-5cb13f027b84-01245`, `m-5cb13f027b84-01253`, `m-5cb13f027b84-01286`, `m-5cb13f027b84-01303`, `m-5cb13f027b84-01313`, `m-5cb13f027b84-01320`, `m-5cb13f027b84-01288`, `m-5cb13f027b84-01315`

## Status timeline

One character per minute: `?` insufficient evidence, `.` no change, `c` candidate, `S` sustained change.

```
NBH P1: ???????????????????????????????...............
NBH P2: ???????????.............??.?.??.?.????????????...
KES P1: ??????????????????????????????????????????????
KES P2: ?????c?.??.?...???????????ccSc?....?.....??..c??c
```

## Candidate and sustained ticks

| Minute | Team | Status | Direction | Primary z | Ratio | Reason |
|---|---|---|---|---:|---:|---|
| 51' | KES | candidate | increase | 2.36 | 6.00 | primary signal met; missing a corroborating signal |
| 72' | KES | candidate | increase | 3.41 | 4.91 | all conditions met for 1/3 ticks |
| 73' | KES | candidate | increase | 3.41 | 4.91 | all conditions met for 2/3 ticks |
| 74' | KES | sustained_change | increase | 3.41 | 4.91 | sustained change: all conditions met on 3 consecutive ticks; corroborated by opp_defensive_third_completion_z |
| 75' | KES | candidate | increase | 3.00 | 4.17 | primary signal met; missing a corroborating signal |
| 91' | KES | candidate | increase | 2.43 | 2.60 | primary signal met; missing a corroborating signal |
| 94' | KES | candidate | increase | 2.40 | 2.40 | primary signal met; missing a corroborating signal |

## Rolling metrics every 5 minutes (last 10 minutes)

| Minute | Team | High pressures | Opp build-up passes | High press / build-up pass | High regains | Opp def-third completion | Opp long share | Opp keeper long share | High press / opp controlled min |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5' | NBH | 2 | 8 | n/a | 1 | n/a | 0.10 | n/a | n/a |
| 5' | KES | 0 | 9 | n/a | 0 | n/a | 0.05 | n/a | 0.00 |
| 10' | NBH | 5 | 20 | 0.25 | 2 | 0.80 | 0.10 | 0.20 | 2.01 |
| 10' | KES | 0 | 12 | 0.00 | 1 | 0.92 | 0.08 | n/a | 0.00 |
| 15' | NBH | 4 | 19 | 0.21 | 1 | 0.89 | 0.07 | 0.25 | 1.13 |
| 15' | KES | 2 | 16 | 0.12 | 3 | 0.88 | 0.11 | 0.00 | 0.80 |
| 20' | NBH | 1 | 14 | 0.07 | 0 | 0.79 | 0.04 | n/a | 0.36 |
| 20' | KES | 2 | 13 | 0.15 | 2 | 0.92 | 0.12 | n/a | 0.64 |
| 25' | NBH | 2 | 18 | 0.11 | 1 | 0.67 | 0.12 | 0.50 | 0.96 |
| 25' | KES | 0 | 8 | n/a | 1 | n/a | 0.08 | n/a | 0.00 |
| 30' | NBH | 5 | 21 | 0.24 | 3 | 0.81 | 0.16 | 0.67 | 1.45 |
| 30' | KES | 0 | 15 | 0.00 | 2 | 0.87 | 0.03 | n/a | 0.00 |
| 35' | NBH | 8 | 23 | 0.35 | 2 | 0.83 | 0.15 | n/a | 2.66 |
| 35' | KES | 0 | 9 | n/a | 1 | n/a | 0.06 | n/a | 0.00 |
| 40' | NBH | 7 | 28 | 0.25 | 0 | 0.82 | 0.15 | n/a | 2.18 |
| 40' | KES | 0 | 4 | n/a | 0 | n/a | 0.08 | n/a | 0.00 |
| 45' | NBH | 2 | 21 | 0.10 | 1 | 0.81 | 0.17 | n/a | 0.60 |
| 45' | KES | 2 | 4 | n/a | 0 | n/a | 0.16 | n/a | 0.81 |
| 50' | NBH | 0 | 13 | 0.00 | 1 | 0.85 | 0.12 | 0.33 | 0.00 |
| 50' | KES | 3 | 12 | 0.25 | 1 | 0.75 | 0.13 | n/a | 1.12 |
| 55' | NBH | 2 | 13 | 0.15 | 1 | 0.92 | 0.06 | 0.00 | 0.73 |
| 55' | KES | 2 | 13 | 0.15 | 2 | 0.85 | 0.06 | n/a | 0.76 |
| 60' | NBH | 5 | 16 | 0.31 | 2 | 0.81 | 0.09 | n/a | 1.68 |
| 60' | KES | 2 | 17 | 0.12 | 3 | 0.82 | 0.11 | n/a | 0.75 |
| 65' | NBH | 6 | 24 | 0.25 | 2 | 0.75 | 0.17 | n/a | 2.35 |
| 65' | KES | 1 | 9 | n/a | 2 | n/a | 0.09 | n/a | 0.30 |
| 70' | NBH | 3 | 18 | 0.17 | 1 | 0.67 | 0.20 | n/a | n/a |
| 70' | KES | 5 | 9 | n/a | 1 | n/a | 0.08 | n/a | 1.52 |
| 75' | NBH | 4 | 14 | 0.29 | 1 | 0.79 | 0.16 | n/a | n/a |
| 75' | KES | 8 | 20 | 0.40 | 2 | 0.70 | 0.09 | 0.25 | 2.73 |
| 80' | NBH | 4 | 15 | 0.27 | 1 | 0.93 | 0.10 | n/a | 1.66 |
| 80' | KES | 6 | 20 | 0.30 | 1 | 0.80 | 0.06 | 0.20 | 2.30 |
| 85' | NBH | 0 | 8 | n/a | 0 | n/a | 0.03 | n/a | 0.00 |
| 85' | KES | 5 | 16 | 0.31 | 0 | 0.88 | 0.10 | 0.25 | 1.61 |
| 90' | NBH | 0 | 14 | 0.00 | 1 | 0.86 | 0.02 | 0.00 | 0.00 |
| 90' | KES | 9 | 22 | 0.41 | 2 | 0.86 | 0.07 | n/a | 2.44 |
