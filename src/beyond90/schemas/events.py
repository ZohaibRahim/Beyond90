"""Public synthetic football event schema, version 1.

This is the ONLY data the live analytics system may observe. It deliberately
contains no tactical-intervention metadata, and every model rejects unknown
fields, so hidden simulator state cannot ride along inside an event.

Conventions:
- Coordinates are metres on a 105 x 68 pitch, normalised so the acting team
  (``team_id``) always attacks toward x = 105.
- ``period`` + ``clock_ms`` give match time; ``sequence`` is the authoritative order.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

EVENT_SCHEMA_VERSION = "1.0.0"

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PitchLocation(_Frozen):
    x: float = Field(ge=0.0, le=PITCH_LENGTH_M)
    y: float = Field(ge=0.0, le=PITCH_WIDTH_M)


class _EventBase(_Frozen):
    schema_version: Literal["1.0.0"] = EVENT_SCHEMA_VERSION
    event_id: Identifier
    match_id: Identifier
    sequence: int = Field(ge=0, description="Strictly increasing order within a match.")
    period: Literal[1, 2]
    clock_ms: int = Field(ge=0, description="Milliseconds since the start of the period.")
    team_id: Identifier = Field(description="Team performing the action.")
    related_event_id: Identifier | None = Field(
        default=None, description="An EARLIER event this one follows from (never a future event)."
    )


class PassOutcome(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    OUT_OF_PLAY = "out_of_play"
    OFFSIDE = "offside"


class PassEvent(_EventBase):
    event_type: Literal["pass"] = "pass"
    player_id: Identifier
    location: PitchLocation
    end_location: PitchLocation
    outcome: PassOutcome
    recipient_id: Identifier | None = None

    @model_validator(mode="after")
    def _check_recipient(self) -> PassEvent:
        if self.outcome is PassOutcome.COMPLETE and self.recipient_id is None:
            raise ValueError("a complete pass requires recipient_id")
        if self.outcome is not PassOutcome.COMPLETE and self.recipient_id is not None:
            raise ValueError("only a complete pass may have recipient_id")
        if self.recipient_id == self.player_id:
            raise ValueError("a player cannot pass to themselves")
        return self


class ShotOutcome(StrEnum):
    GOAL = "goal"
    SAVED = "saved"
    OFF_TARGET = "off_target"
    BLOCKED = "blocked"
    WOODWORK = "woodwork"


class BodyPart(StrEnum):
    RIGHT_FOOT = "right_foot"
    LEFT_FOOT = "left_foot"
    HEAD = "head"
    OTHER = "other"


class ShotEvent(_EventBase):
    event_type: Literal["shot"] = "shot"
    player_id: Identifier
    location: PitchLocation
    outcome: ShotOutcome
    body_part: BodyPart


class TackleOutcome(StrEnum):
    WON = "won"
    LOST = "lost"


class TackleEvent(_EventBase):
    event_type: Literal["tackle"] = "tackle"
    player_id: Identifier
    opponent_player_id: Identifier
    location: PitchLocation
    outcome: TackleOutcome

    @model_validator(mode="after")
    def _check_players(self) -> TackleEvent:
        if self.player_id == self.opponent_player_id:
            raise ValueError("a player cannot tackle themselves")
        return self


class PressureEvent(_EventBase):
    """A defender closing down an opponent in possession (no ball contact)."""

    event_type: Literal["pressure"] = "pressure"
    player_id: Identifier
    opponent_player_id: Identifier
    location: PitchLocation
    duration_ms: int = Field(gt=0, le=10_000)

    @model_validator(mode="after")
    def _check_players(self) -> PressureEvent:
        if self.player_id == self.opponent_player_id:
            raise ValueError("a player cannot pressure themselves")
        return self


class InterceptionEvent(_EventBase):
    event_type: Literal["interception"] = "interception"
    player_id: Identifier
    location: PitchLocation


class PossessionChangeCause(StrEnum):
    KICKOFF = "kickoff"
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    INCOMPLETE_PASS = "incomplete_pass"
    OUT_OF_PLAY = "out_of_play"
    SHOT = "shot"
    GOAL_CONCEDED = "goal_conceded"
    FOUL = "foul"


class PossessionChangeEvent(_EventBase):
    """``team_id`` is the team GAINING possession."""

    event_type: Literal["possession_change"] = "possession_change"
    previous_team_id: Identifier | None = Field(
        default=None, description="None only at a period kickoff."
    )
    cause: PossessionChangeCause
    player_id: Identifier | None = Field(default=None, description="Player gaining the ball, if any.")
    location: PitchLocation

    @model_validator(mode="after")
    def _check_teams(self) -> PossessionChangeEvent:
        if self.previous_team_id == self.team_id:
            raise ValueError("possession must change to a different team")
        if self.previous_team_id is None and self.cause is not PossessionChangeCause.KICKOFF:
            raise ValueError("previous_team_id may be omitted only for a kickoff")
        return self


class SubstitutionEvent(_EventBase):
    event_type: Literal["substitution"] = "substitution"
    player_off_id: Identifier
    player_on_id: Identifier

    @model_validator(mode="after")
    def _check_players(self) -> SubstitutionEvent:
        if self.player_off_id == self.player_on_id:
            raise ValueError("player_on_id must differ from player_off_id")
        return self


MatchEvent = Annotated[
    Union[
        PassEvent,
        ShotEvent,
        TackleEvent,
        PressureEvent,
        InterceptionEvent,
        PossessionChangeEvent,
        SubstitutionEvent,
    ],
    Field(discriminator="event_type"),
]

EventAdapter: TypeAdapter[MatchEvent] = TypeAdapter(MatchEvent)


class EventSequenceError(ValueError):
    """Raised when a list of events is not a valid chronological match stream."""


def validate_event_sequence(events: Iterable[MatchEvent]) -> Sequence[MatchEvent]:
    """Check stream-level invariants that a single event cannot check on its own.

    - one match_id, unique event_ids
    - strictly increasing ``sequence``
    - time never goes backwards (period, then clock_ms)
    - ``related_event_id`` refers only to an earlier event (no future references)
    """
    result = list(events)
    seen_ids: set[str] = set()
    prev: MatchEvent | None = None
    for event in result:
        if prev is not None:
            if event.match_id != prev.match_id:
                raise EventSequenceError(f"{event.event_id}: mixed match_id")
            if event.sequence <= prev.sequence:
                raise EventSequenceError(f"{event.event_id}: sequence not strictly increasing")
            if (event.period, event.clock_ms) < (prev.period, prev.clock_ms):
                raise EventSequenceError(f"{event.event_id}: match time went backwards")
        if event.event_id in seen_ids:
            raise EventSequenceError(f"{event.event_id}: duplicate event_id")
        if event.related_event_id is not None and event.related_event_id not in seen_ids:
            raise EventSequenceError(
                f"{event.event_id}: related_event_id {event.related_event_id!r} is not an earlier event"
            )
        seen_ids.add(event.event_id)
        prev = event
    return result
