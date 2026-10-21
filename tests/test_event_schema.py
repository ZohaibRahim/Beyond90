import pytest
from pydantic import ValidationError

from beyond90.schemas import (
    EVENT_SCHEMA_VERSION,
    EventAdapter,
    EventSequenceError,
    FoulEvent,
    InterceptionEvent,
    PassEvent,
    PeriodEndEvent,
    PossessionChangeEvent,
    PressureEvent,
    RestartEvent,
    ShotEvent,
    SubstitutionEvent,
    TackleEvent,
    validate_event_sequence,
)

LOC = {"x": 50.0, "y": 34.0}

VALID_EVENTS = {
    "pass": dict(team_id="nbh", player_id="p1", location=LOC, end_location={"x": 60, "y": 30},
                 outcome="complete", recipient_id="p2"),
    "shot": dict(team_id="nbh", player_id="p9", location={"x": 94, "y": 34}, outcome="saved",
                 body_part="left_foot"),
    "tackle": dict(team_id="nbh", player_id="p4", opponent_player_id="q7", location=LOC, outcome="won"),
    "pressure": dict(team_id="nbh", player_id="p8", opponent_player_id="q6", location=LOC, duration_ms=1200),
    "interception": dict(team_id="nbh", player_id="p5", location=LOC),
    "possession_change": dict(team_id="nbh", previous_team_id="kes", cause="interception", location=LOC),
    "foul": dict(team_id="nbh", player_id="p4", opponent_player_id="q7", location=LOC),
    "restart": dict(team_id="nbh", restart_type="throw_in", player_id="p3", location={"x": 30, "y": 0}),
    "substitution": dict(team_id="nbh", player_off_id="p10", player_on_id="p14"),
    "period_end": dict(),
}

EXPECTED_CLASS = {
    "pass": PassEvent, "shot": ShotEvent, "tackle": TackleEvent, "pressure": PressureEvent,
    "interception": InterceptionEvent, "possession_change": PossessionChangeEvent, "foul": FoulEvent,
    "restart": RestartEvent, "substitution": SubstitutionEvent, "period_end": PeriodEndEvent,
}


def ev(event_type: str, seq: int, clock_ms: int = 0, **fields):
    data = {"match_id": "m001", "period": 1, "event_type": event_type, "event_id": f"e{seq:05d}",
            "sequence": seq, "clock_ms": clock_ms, **fields}
    return EventAdapter.validate_python(data)


def valid(event_type: str, seq: int = 1, clock_ms: int = 0, **overrides):
    return ev(event_type, seq, clock_ms, **{**VALID_EVENTS[event_type], **overrides})


def test_every_event_model_is_covered():
    assert set(EXPECTED_CLASS) == set(VALID_EVENTS)


@pytest.mark.parametrize("event_type", sorted(VALID_EVENTS))
def test_each_event_type_parses_to_its_model(event_type):
    event = valid(event_type)
    assert isinstance(event, EXPECTED_CLASS[event_type])
    assert event.schema_version == EVENT_SCHEMA_VERSION == "2.0.0"


@pytest.mark.parametrize("event_type", sorted(VALID_EVENTS))
def test_json_round_trip(event_type):
    event = valid(event_type)
    assert EventAdapter.validate_json(event.model_dump_json()) == event


def test_unknown_event_type_rejected():
    with pytest.raises(ValidationError):
        ev("dribble", 1, team_id="nbh", player_id="p1", location=LOC)


@pytest.mark.parametrize("field", ["intervention_id", "xg", "pass_difficulty", "pressing_intensity"])
def test_unknown_fields_rejected_so_hidden_metadata_cannot_leak(field):
    with pytest.raises(ValidationError):
        valid("pressure", **{field: 1})


def test_period_end_has_no_team():
    with pytest.raises(ValidationError):
        valid("period_end", team_id="nbh")


def test_wrong_schema_version_rejected():
    with pytest.raises(ValidationError):
        valid("interception", schema_version="1.0.0")


def test_events_are_immutable():
    event = valid("interception")
    with pytest.raises(ValidationError):
        event.team_id = "other"


@pytest.mark.parametrize("loc", [{"x": -0.1, "y": 10}, {"x": 105.1, "y": 10}, {"x": 10, "y": 68.5}])
def test_location_must_be_on_pitch(loc):
    with pytest.raises(ValidationError):
        valid("interception", location=loc)


@pytest.mark.parametrize("field,value", [("period", 3), ("clock_ms", -1), ("sequence", -1),
                                         ("event_id", "bad id!")])
def test_base_field_constraints(field, value):
    data = {"match_id": "m001", "period": 1, "event_type": "interception", "event_id": "e1", "sequence": 1,
            "clock_ms": 0, **VALID_EVENTS["interception"], field: value}
    with pytest.raises(ValidationError):
        EventAdapter.validate_python(data)


def test_complete_pass_requires_recipient():
    with pytest.raises(ValidationError, match="requires recipient_id"):
        valid("pass", recipient_id=None)


def test_incomplete_pass_cannot_have_recipient():
    with pytest.raises(ValidationError, match="only a complete pass"):
        valid("pass", outcome="incomplete")


def test_pass_to_self_rejected():
    with pytest.raises(ValidationError, match="themselves"):
        valid("pass", recipient_id="p1")


@pytest.mark.parametrize("event_type", ["tackle", "pressure", "foul"])
def test_cannot_act_on_self(event_type):
    with pytest.raises(ValidationError, match="themselves"):
        valid(event_type, opponent_player_id=VALID_EVENTS[event_type]["player_id"])


def test_pressure_duration_must_be_positive():
    with pytest.raises(ValidationError):
        valid("pressure", duration_ms=0)


def test_substitution_requires_different_players():
    with pytest.raises(ValidationError, match="must differ"):
        valid("substitution", player_on_id="p10")


def test_possession_change_must_switch_team():
    with pytest.raises(ValidationError, match="different team"):
        valid("possession_change", previous_team_id="nbh")


def test_possession_change_requires_previous_team():
    data = {k: v for k, v in VALID_EVENTS["possession_change"].items() if k != "previous_team_id"}
    with pytest.raises(ValidationError):
        ev("possession_change", 1, **data)


def test_unknown_restart_type_rejected():
    with pytest.raises(ValidationError):
        valid("restart", restart_type="penalty")


# --- structural stream validation ---------------------------------------------

def _stream():
    return [
        valid("restart", 0, 0, restart_type="kickoff", location={"x": 52.5, "y": 34}),
        valid("pass", 1, 1500),
        valid("tackle", 2, 4000, team_id="kes"),
        valid("possession_change", 3, 4000, team_id="kes", previous_team_id="nbh", cause="tackle",
              related_event_id="e00002"),
    ]


def test_valid_stream_passes():
    assert len(validate_event_sequence(_stream())) == 4


def test_stream_rejects_non_increasing_sequence():
    s = _stream()
    s[2], s[3] = s[3], s[2]
    with pytest.raises(EventSequenceError):
        validate_event_sequence(s)


def test_stream_rejects_time_going_backwards():
    with pytest.raises(EventSequenceError, match="backwards"):
        validate_event_sequence(_stream() + [valid("interception", 4, 3000)])


def test_stream_allows_clock_reset_in_new_period():
    assert len(validate_event_sequence(_stream() + [valid("period_end", 4, 5000),
                                                    valid("interception", 5, 0, period=2)])) == 6


def test_stream_rejects_duplicate_event_id():
    s = _stream()
    dup = s[1].model_copy(update={"sequence": 10, "clock_ms": 9000})
    with pytest.raises(EventSequenceError, match="duplicate"):
        validate_event_sequence(s + [dup])


def test_stream_rejects_reference_to_future_event():
    s = _stream()
    s[1] = s[1].model_copy(update={"related_event_id": "e00003"})
    with pytest.raises(EventSequenceError, match="not an earlier event"):
        validate_event_sequence(s)


def test_stream_rejects_mixed_matches():
    s = _stream()
    s[3] = s[3].model_copy(update={"match_id": "m002"})
    with pytest.raises(EventSequenceError, match="match_id"):
        validate_event_sequence(s)
