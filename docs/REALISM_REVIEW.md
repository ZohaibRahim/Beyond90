# Realism review — seed 42 (after Stage 2.6)

For the project owner's football judgments. Claude has listed measured facts and open questions only; every "Your assessment" field is intentionally blank.

Materials:
- Public match report: `reports/public/match_report_seed42.md`
- Private evaluation record (hidden script and paired control): `reports/private/evaluation_seed42.md`
- 30-seed intervention review: `reports/private/intervention_review.md`
- Regenerate: `PYTHONPATH=src .venv/Scripts/python -m beyond90.simulator --seed 42 --review 30`

Note: the Stage 2.6 engine fix changes the random draws after the first affected pass, so seed 42 is now a different match (NBH 1–3 KES) from the one reviewed before. The old 29th-minute sequence no longer exists; the defect is covered by a multi-seed regression test.

## Owner's earlier review notes (Stage 2.5)

- Time accounting presentation was not mutually exclusive. Addressed in Stage 2.6.
- Northbridge 29' sequence (events 573–589) had implausible passing on the goal line. Addressed in Stage 2.6.
- The seed-42 winning goal began near Kestrel Bay's own goal; it must not be attributed to the high press.

## Open questions

1. **Ball-in-play time.** Mean 61.4 min per match over 20 seeds (57.8–64.8); seed 42: 62:20. Stoppages average 33.7 min.
   Your assessment:

2. **Scoring.** 1.9 goals per match after removing the goal-line artifact (11.2 shots and 4.0 on target per team). Shot conversion has not been retuned.
   Your assessment:

3. **Goalkeeper involvement.** About 15.6 passes received by goalkeepers per match (both teams), all from deliberate back passes.
   Your assessment:

4. **Fouls under a high press.** Unchanged after the switch (0.111 vs 0.109 per min).
   Your assessment:

5. **Chance creation under a high press.** Pressing team shots per min 1.6× control; pressed team 0.88×.
   Your assessment:

6. **Strength of the positive control.** Attacking-third pressures 3.4×; pressed-team completion from own third 82.1% → 76.2%; sequences 4.2 → 3.6 passes.
   Your assessment:

7. **Final-third passing after the fix.** 2.5% of completed passes end within 7 m of the goal line; cut-backs are pulled toward the centre of the box.
   Your assessment:

8. **Set pieces and substitutions.** 5.9 corners, 19.6 throw-ins and 5.0 goal kicks per team; 3–5 second-half substitutions, like-for-like.
   Your assessment:

9. **Anything else in the regenerated report** (time table, sequences, goal build-ups).
   Your assessment:
