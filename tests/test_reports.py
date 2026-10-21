from beyond90.reporting import UNSUPPORTED_MECHANICS, render_match_report
from beyond90.simulator import simulate_match
from beyond90.simulator.evaluation import intervention_review, render_evaluation_record


def test_public_report_sections():
    r = simulate_match(42)
    report = render_match_report(r.setup, r.events)
    for heading in ("## Line-ups and shape", "## Goals", "## Substitutions", "## Team statistics (full match)",
                    "## 15-minute trends", "## Possession sequences", "## Build-up to goals",
                    "## Unsupported match mechanics"):
        assert heading in report, heading
    assert "shape from listed positions: 4-3-3" in report
    assert "possession (time-based estimate)" in report and "pass share (not possession)" in report
    assert all(line in report for line in UNSUPPORTED_MECHANICS)


def test_private_records_are_marked_and_complete():
    r = simulate_match(42)
    record = render_evaluation_record(r)
    assert record.startswith("# PRIVATE")
    assert r.ground_truth.applied[0].first_event_id in record
    review = intervention_review(range(3))
    assert review.startswith("# PRIVATE") and "Scripted / control" in review


def test_apportion_sums_exactly():
    from beyond90.reporting.match_report import apportion

    assert apportion([1814_400, 1579_900, 346_500, 2046_400], 5787) == [1814, 1580, 347, 2046]
    assert sum(apportion([1, 1, 1], 100)) == 100
    assert apportion([0, 0], 10) == [0, 0]


def test_time_table_rows_add_up_to_displayed_total():
    import re

    for seed in (0, 42, 7):
        r = simulate_match(seed)
        report = render_match_report(r.setup, r.events)
        table = report.split("## Time accounting")[1].split("Ball in play")[0]
        times = [int(m) * 60 + int(s) for m, s in re.findall(r"\| \**(\d+):(\d\d)\** \|", table)]
        *rows, total = times
        assert len(rows) == 4 and sum(rows) == total
        shares = [float(x) for x in re.findall(r"\| (\d+\.\d)% \|", table)][:-1]
        assert round(sum(shares), 1) == 100.0
