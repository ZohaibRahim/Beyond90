"""Hand-built public event streams for tests."""

from beyond90.schemas import EventAdapter, MatchStateTracker
from beyond90.simulator.teams import build_match_setup

SETUP = build_match_setup("t-001")  # nbh attacks x=105 in period 1; kes kicks off period 1
CENTRE = {"x": 52.5, "y": 34.0}


class Stream:
    def __init__(self, setup=SETUP):
        self.setup = setup
        self.tracker = MatchStateTracker(setup)
        self.events = []
        self.period, self.clock = 1, 0

    def add(self, event_type, **fields):
        self.clock = fields.pop("clock_ms", self.clock + 1000)
        self.period = fields.pop("period", self.period)
        seq = len(self.events)
        event = EventAdapter.validate_python({
            "event_type": event_type, "event_id": f"e{seq:04d}", "match_id": self.setup.match_id,
            "sequence": seq, "period": self.period, "clock_ms": self.clock, **fields})
        self.tracker.apply(event)
        self.events.append(event)
        return self

    # Shorthand builders.
    def kickoff(self, team, player, **kw):
        return self.add("restart", team_id=team, restart_type="kickoff", player_id=player, location=CENTRE, **kw)

    def pass_(self, team, player, to=None, outcome="complete", start=(50, 34), end=(55, 30), **kw):
        return self.add("pass", team_id=team, player_id=player, recipient_id=to, outcome=outcome,
                        location={"x": start[0], "y": start[1]}, end_location={"x": end[0], "y": end[1]}, **kw)

    def end_period(self, period):
        return self.add("period_end", clock_ms=45 * 60_000 + 30_000, period=period)
