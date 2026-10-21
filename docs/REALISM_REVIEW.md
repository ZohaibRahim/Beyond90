# Realism review — seed 42 (simulator 0.1.0)

For the project owner's football judgments. Claude has listed measured facts and open questions only; every "Your assessment" field is intentionally blank.

Materials:
- Public match report: `reports/public/match_report_seed42.md`
- Private evaluation record (hidden script and paired control): `reports/private/evaluation_seed42.md`
- 30-seed intervention review: `reports/private/intervention_review.md`
- Regenerate: `PYTHONPATH=src .venv/Scripts/python -m beyond90.simulator --seed 42 --review 30`

## Open questions

1. **Ball-in-play time.** Mean 63.0 min per match over 20 seeds (range 55.7–69.8); seed 42 has 71:54.
   Your assessment:

2. **Goalkeeper involvement.** About 14 passes received by goalkeepers per match (both teams) and about 15 passes made per keeper. Receptions come only from deliberate back passes, which are more likely for defenders, deep and under pressure.
   Your assessment:

3. **Fouls under a high press.** The pressing team's foul rate did not change after the switch (0.099/min scripted vs 0.099 control).
   Your assessment:

4. **Chance creation under a high press.** After the switch, the pressing team's shots/min rose 1.48× and the pressed team's fell to 0.75×. There is only a small "space behind the press" effect (an extra carry after a pass that beats pressure).
   Your assessment:

5. **Strength of the positive control.** Attacking-third pressures about 3.1×; pressed-team completion −4.5 points; sequences 4.2 → 3.5 passes.
   Your assessment:

6. **Volume and rhythm.** About 503 passes per team at 78% completion, about 255 possession sequences per match with a mean of 4 passes, and 15-minute possession swings between 38% and 62% in seed 42.
   Your assessment:

7. **Set pieces.** 6.8 corners, 17.5 throw-ins and 5.5 goal kicks per team per match.
   Your assessment:

8. **Substitutions.** 3–5 per team, all in the second half (some at half-time), like-for-like.
   Your assessment:

9. **Anything else in the report that looks wrong to a football eye** (sequence build-ups, goal build-ups, player involvement by position).
   Your assessment:
