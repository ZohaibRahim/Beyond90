"""As-of-time access to a public event stream.

Observability semantics. An event's ``(period, clock_ms)`` is when the action
STARTED, which is not always when all of its fields could be known:

- ``pass``: struck at ``clock_ms``; its outcome, end location and recipient are
  resolved only when the ball arrives. The next event in the stream bounds that
  moment, so a pass is released at the next event's start time. A pass with no
  following event yet is unresolved and NOT released.
- ``pressure``: begins at ``clock_ms``; ``duration_ms`` is known only when the
  pressure ends, so it is released at ``clock_ms + duration_ms``.
- every other event is complete at its own timestamp.

Events are delivered in sequence order: no event is released before its
predecessor. The events visible at a time T are therefore always a PREFIX of the
stream, and depend only on events that started at or before T.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from typing import NamedTuple

from beyond90.schemas import MatchEvent, PassEvent, PressureEvent


class MatchTime(NamedTuple):
    period: int
    clock_ms: int


def event_time(event: MatchEvent) -> MatchTime:
    return MatchTime(event.period, event.clock_ms)


def _own_release(event: MatchEvent, following: MatchEvent | None) -> MatchTime | None:
    if isinstance(event, PassEvent):
        return event_time(following) if following is not None else None
    if isinstance(event, PressureEvent):
        return MatchTime(event.period, event.clock_ms + event.duration_ms)
    return event_time(event)


def release_times(events: Sequence[MatchEvent]) -> list[MatchTime | None]:
    """When each event becomes fully observable (None = not yet resolvable from this stream)."""
    out: list[MatchTime | None] = []
    latest: MatchTime | None = MatchTime(0, 0)
    for i, event in enumerate(events):
        own = _own_release(event, events[i + 1] if i + 1 < len(events) else None)
        if own is None or latest is None:
            latest = None  # an unresolved event blocks everything after it
        else:
            latest = max(latest, own)
        out.append(latest)
    return out


class AsOfFeed:
    """The live system's view of a match at any time T: only events fully observable by T."""

    def __init__(self, events: Sequence[MatchEvent]) -> None:
        self._events = tuple(events)
        releases = release_times(self._events)
        self._released = [r for r in releases if r is not None]  # non-decreasing prefix

    def visible(self, as_of: MatchTime) -> tuple[MatchEvent, ...]:
        return self._events[: bisect_right(self._released, as_of)]

    def release_time(self, index: int) -> MatchTime | None:
        return self._released[index] if index < len(self._released) else None
