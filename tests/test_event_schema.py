import pytest
from pydantic import ValidationError

from beyond90.schemas import (
    EVENT_SCHEMA_VERSION,
    EventAdapter,
    EventSequenceError,
    InterceptionEvent,
    PassEvent,
    PossessionChangeEvent,
    PressureEvent,
    ShotEvent,
    SubstitutionEvent,
    TackleEvent,
    validate_event_sequence,
)

BASE = {"match_id": "m001", "period": 1, "team_id": "harbour_fc"}


def ev(event_type: str, seq: int, clock_ms: int = 0, **fields):
    return EventAdapter.validate_python(
        {**BASE, "event_type": event_type, "event_id": f"e{seq:05d}", "sequence": seq,
         "clock_ms": clock_ms, **fields}
    )


LOC = {"x": 50.0, "y": 34.0}

VALID_EVENTS = {
    "pass": dict(player_id="p1", location=LOC, end_location={"x": 60, "y": 30},
                 outcome="complete", recipient_id="p2"),
    "shot": dict(player_id="p9", location={"x": 94, "y": 34}, outcome="saved", body_part="left_foot"),
    "tackle": dict(player_id="p4", opponent_player_id="q7", location=LOC, outcome="won"),
    "pressure": dict(player_id="p8", opponent_player_id="q6", location=LOC, duration_ms=1200),
    "interception": dict(player_id="p5", location=LOC),
    "possession_change": dict(previous_team_id="river_utd", cause="interception", location=LOC),
    "substitution": dict(player_off_id="p10", player_on_id="p14"),
}

EXPECTED_CLASS = {
    "pass": PassEvent, "shot": ShotEvent, "tackle": TackleEvent, "pressure": PressureEvent,
    "interception": InterceptionEvent, "possession_change": PossessionChangeEvent,
    "substitution": SubstitutionEvent,
}


@pytest.mark.parametrize("event_type", sorted(VALID_EVENTS))
def test_each_event_type_parses_to_its_model(event_type):
    event = ev(event_type, 1, **VALID_EVENTS[event_type])
    assert isinstance(event, EXPECTED_CLASS[event_type])
    assert event.schema_version == EVENT_SCHEMA_VERSION


@pytest.mark.parametrize("event_type", sorted(VALID_EVENTS))
def test_json_round_trip(event_type):
    event = ev(event_type, 1, **VALID_EVENTS[event_type])
    assert EventAdapter.validate_json(event.model_dump_json()) == event


def test_unknown_event_type_rejected():
    with pytest.raises(ValidationError):
        ev("dribble", 1, player_id="p1", location=LOC)


def test_unknown_fields_rejected_so_hidden_metadata_cannot_leak():
    with pytest.raises(ValidationError):
        ev("pressure", 1, **VALID_EVENTS["pressure"], intervention_id="int-1")


def test_wrong_schema_version_rejected():
    with pytest.raises(ValidationError):
        ev("interception", 1, **VALID_EVENTS["interception"], schema_version="2.0.0")


def test_events_are_immutable():
    event = ev("interception", 1, **VALID_EVENTS["interception"])
    with pytest.raises(ValidationError):
        event.team_id = "other"


@pytest.mark.parametrize("loc", [{"x": -0.1, "y": 10}, {"x": 105.1, "y": 10}, {"x": 10, "y": 68.5}])
def test_location_must_be_on_pitch(loc):
    with pytest.raises(ValidationError):
        ev("interception", 1, player_id="p5", location=loc)


@pytest.mark.parametrize("field,value", [("period", 3), ("clock_ms", -1), ("sequence", -1),
                                         ("event_id", "bad id!")])
def test_base_field_constraints(field, value):
    data = {**BASE, "event_type": "interception", "event_id": "e1", "sequence": 1, "clock_ms": 0,
            **VALID_EVENTS["interception"], field: value}
    with pytest.raises(ValidationError):
        EventAdapter.validate_python(data)


def test_complete_pass_requires_recipient():
    fields = {**VALID_EVENTS["pass"], "recipient_id": None}
    with pytest.raises(ValidationError, match="requires recipient_id"):
        ev("pass", 1, **fields)


def test_incomplete_pass_cannot_have_recipient():
    fields = {**VALID_EVENTS["pass"], "outcome": "incomplete"}
    with pytest.raises(ValidationError, match="only a complete pass"):
        ev("pass", 1, **fields)


def test_pass_to_self_rejected():
    fields = {**VALID_EVENTS["pass"], "recipient_id": "p1"}
    with pytest.raises(ValidationError, match="themselves"):
        ev("pass", 1, **fields)


@pytest.mark.parametrize("event_type", ["tackle", "pressure"])
def test_cannot_act_on_self(event_type):
    fields = {**VALID_EVENTS[event_type], "opponent_player_id": VALID_EVENTS[event_type]["player_id"]}
    with pytest.raises(ValidationError, match="themselves"):
        ev(event_type, 1, **fields)


def test_pressure_duration_must_be_positive():
    with pytest.raises(ValidationError):
        ev("pressure", 1, **{**VALID_EVENTS["pressure"], "duration_ms": 0})


def test_substitution_requires_different_players():
    with pytest.raises(ValidationError, match="must differ"):
        ev("substitution", 1, player_off_id="p10", player_on_id="p10")


def test_possession_change_must_switch_team():
    with pytest.raises(ValidationError, match="different team"):
        ev("possession_change", 1, **{**VALID_EVENTS["possession_change"], "previous_team_id": "harbour_fc"})


def test_possession_change_without_previous_team_only_at_kickoff():
    ok = ev("possession_change", 0, cause="kickoff", location=LOC)
    assert ok.previous_team_id is None
    with pytest.raises(ValidationError, match="only for a kickoff"):
        ev("possession_change", 0, cause="tackle", location=LOC)


# --- stream-level validation -------------------------------------------------

def _stream():
    return [
        ev("possession_change", 0, 0, cause="kickoff", location={"x": 52.5, "y": 34}),
        ev("pass", 1, 1500, **VALID_EVENTS["pass"]),
        ev("tackle", 2, 4000, **{**VALID_EVENTS["tackle"], "team_id": "river_utd"}),
        ev("possession_change", 3, 4000, team_id="river_utd", previous_team_id="harbour_fc",
           cause="tackle", location=LOC, related_event_id="e00002"),
    ]


def test_valid_stream_passes():
    assert len(validate_event_sequence(_stream())) == 4


def test_stream_rejects_non_increasing_sequence():
    s = _stream()
    s[2], s[3] = s[3], s[2]
    with pytest.raises(EventSequenceError):
        validate_event_sequence(s)


def test_stream_rejects_time_going_backwards():
    s = _stream() + [ev("interception", 4, 3000, **VALID_EVENTS["interception"])]
    with pytest.raises(EventSequenceError, match="backwards"):
        validate_event_sequence(s)


def test_stream_allows_clock_reset_in_new_period():
    s = _stream() + [ev("possession_change", 4, 0, period=2, cause="kickoff", location=LOC)]
    assert len(validate_event_sequence(s)) == 5


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
