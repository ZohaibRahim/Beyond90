"""Complete, auditable evidence behind a finding, retrieved on demand.

A ``Finding`` lists only its headline events (high pressures and high regains in the
recent window). ``finding_evidence`` rebuilds the detector's state from exactly the
events released at the finding's detection time and returns every numerator and
denominator event for each window the decision used: baseline, recent 10 minutes,
and both 5-minute halves. The cost is one replay of the visible stream, paid only
when someone asks.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from beyond90.detection.detector import DEFAULT_CONFIG, DetectorConfig, Finding
from beyond90.detection.metrics import RollingState
from beyond90.live.feed import AsOfFeed, MatchTime
from beyond90.schemas import MatchEvent, MatchSetup


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WindowEvidence(_Model):
    start_ms: int
    end_ms: int
    counts: dict[str, int | float]
    event_ids: dict[str, tuple[str, ...]]


class FindingEvidence(_Model):
    match_id: str
    team_id: str
    detected_period: int
    detected_clock_ms: int
    released_event_count: int
    baseline: WindowEvidence
    recent: WindowEvidence
    recent_first_half: WindowEvidence
    recent_second_half: WindowEvidence


def _window(state: RollingState, team: str, start: int, end: int) -> WindowEvidence:
    w = state.window(team, start, end)
    counts = {k: v for k, v in w.as_dict().items() if not k.endswith(("_ms", "_share", "_completion"))
              and "_per_" not in k}
    ids = {k: tuple(v) for k, v in state.evidence(team, start, end).items()}
    return WindowEvidence(start_ms=w.start_ms, end_ms=end, counts=counts, event_ids=ids)


def finding_evidence(setup: MatchSetup, events: Sequence[MatchEvent], finding: Finding,
                     config: DetectorConfig = DEFAULT_CONFIG) -> FindingEvidence:
    at = MatchTime(finding.detected_period, finding.detected_clock_ms)
    visible = AsOfFeed(events).visible(at)
    state = RollingState(setup)
    for e in visible:
        state.ingest(e)
    now = finding.detected_elapsed_ms
    start, half = now - config.long_window_ms, now - config.short_window_ms
    team = finding.team_id
    return FindingEvidence(
        match_id=setup.match_id, team_id=team, detected_period=at.period, detected_clock_ms=at.clock_ms,
        released_event_count=len(visible),
        baseline=_window(state, team, 0, start), recent=_window(state, team, start, now),
        recent_first_half=_window(state, team, start, half), recent_second_half=_window(state, team, half, now),
    )
