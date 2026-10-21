from functools import cache

import pytest

from beyond90.live.feed import AsOfFeed, MatchTime, event_time, release_times
from beyond90.schemas import PassEvent, PressureEvent
from beyond90.simulator import simulate_match


@cache
def events(seed=42):
    return simulate_match(seed).events


def test_pass_outcome_not_visible_until_next_event():
    evs = events()
    i = next(i for i, e in enumerate(evs) if isinstance(e, PassEvent) and evs[i + 1].clock_ms > e.clock_ms
             and evs[i + 1].period == e.period)
    feed = AsOfFeed(evs)
    assert evs[i] not in feed.visible(event_time(evs[i]))
    assert evs[i] in feed.visible(event_time(evs[i + 1]))


def test_pressure_duration_not_visible_until_pressure_ends():
    evs = events()
    p = next(e for e in evs if isinstance(e, PressureEvent))
    feed = AsOfFeed(evs)
    assert p not in feed.visible(MatchTime(p.period, p.clock_ms + p.duration_ms - 1))
    assert p in feed.visible(MatchTime(p.period, p.clock_ms + p.duration_ms))


def test_unresolved_final_pass_is_never_released():
    evs = events()
    i = next(i for i, e in enumerate(evs) if isinstance(e, PassEvent))
    assert AsOfFeed(evs[: i + 1]).visible(MatchTime(2, 10**9)) == evs[:i]


@pytest.mark.parametrize("seed", [0, 42])
def test_visible_set_is_a_prefix_of_started_events(seed):
    evs = events(seed)
    feed = AsOfFeed(evs)
    releases = release_times(evs)
    assert all(a <= b for a, b in zip(releases, releases[1:]))
    for period in (1, 2):
        for minute in range(0, 50, 3):
            t = MatchTime(period, minute * 60_000 + 123)
            vis = feed.visible(t)
            assert vis == evs[: len(vis)]
            assert all(event_time(e) <= t for e in vis)  # nothing that started after T
            assert all(r <= t for r in releases[: len(vis)])


@pytest.mark.parametrize("seed", [0, 42])
def test_every_event_released_no_earlier_than_it_started_or_resolved(seed):
    evs = events(seed)
    releases = release_times(evs)
    for i, (e, r) in enumerate(zip(evs, releases)):
        assert r is not None or i == len(evs) - 1 and isinstance(e, PassEvent)
        if r is None:
            continue
        assert r >= event_time(e)
        if isinstance(e, PressureEvent):
            assert r >= (e.period, e.clock_ms + e.duration_ms)
        if isinstance(e, PassEvent):
            assert r >= event_time(evs[i + 1])
