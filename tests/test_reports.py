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
