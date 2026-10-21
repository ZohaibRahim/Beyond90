"""Public synthetic football event schema, version 2.

This is the ONLY match data the live analytics system may observe. Events hold
observable facts only: no tactical settings, intervention labels, xG or
difficulty scores. Every model rejects unknown fields, so hidden simulator
state cannot ride along inside an event.

Conventions:
- Coordinates are FIXED (absolute) metres on a 105 x 68 pitch. Which team
  attacks toward x = 105 depends on the period; derive team-relative
  coordinates with ``MatchSetup.to_attacking_frame``.
- ``period`` + ``clock_ms`` give match time; ``sequence`` is the authoritative order.
- Possession changes in open play are always explicit ``possession_change``
  events; dead-ball possession is given by the ``restart`` that resumes play.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

EVENT_SCHEMA_VERSION = "2.0.0"

PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
CENTRE_SPOT = (PITCH_LENGTH_M / 2, PITCH_WIDTH_M / 2)

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PitchLocation(_Frozen):
    x: float = Field(ge=0.0, le=PITCH_LENGTH_M)
    y: float = Field(ge=0.0, le=PITCH_WIDTH_M)


class _EventBase(_Frozen):
    schema_version: Literal["2.0.0"] = EVENT_SCHEMA_VERSION
    event_id: Identifier
    match_id: Identifier
    sequence: int = Field(ge=0, description="Strictly increasing order within a match.")
    period: Literal[1, 2]
    clock_ms: int = Field(ge=0, description="Milliseconds since the start of the period.")
    related_event_id: Identifier | None = Field(
        default=None, description="An EARLIER event this one follows from (never a future event)."
    )


class _TeamEvent(_EventBase):
    team_id: Identifier = Field(description="Team performing the action.")


class PassOutcome(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    OUT_OF_PLAY = "out_of_play"
    OFFSIDE = "offside"


class PassEvent(_TeamEvent):
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


class ShotEvent(_TeamEvent):
    event_type: Literal["shot"] = "shot"
    player_id: Identifier
    location: PitchLocation
    outcome: ShotOutcome
    body_part: BodyPart


class TackleOutcome(StrEnum):
    WON = "won"
    LOST = "lost"


class TackleEvent(_TeamEvent):
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


class PressureEvent(_TeamEvent):
    """A defender closing down the opponent in possession (observable action only)."""

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


class InterceptionEvent(_TeamEvent):
    event_type: Literal["interception"] = "interception"
    player_id: Identifier
    location: PitchLocation


class PossessionChangeCause(StrEnum):
    TACKLE = "tackle"
    INTERCEPTION = "interception"
    INCOMPLETE_PASS = "incomplete_pass"
    SHOT = "shot"


class PossessionChangeEvent(_TeamEvent):
    """Open-play turnover. ``team_id`` is the team GAINING possession."""

    event_type: Literal["possession_change"] = "possession_change"
    previous_team_id: Identifier
    cause: PossessionChangeCause
    player_id: Identifier | None = Field(default=None, description="Player gaining the ball, if any.")
    location: PitchLocation

    @model_validator(mode="after")
    def _check_teams(self) -> PossessionChangeEvent:
        if self.previous_team_id == self.team_id:
            raise ValueError("possession must change to a different team")
        return self


class FoulEvent(_TeamEvent):
    """``team_id``/``player_id`` committed the foul against ``opponent_player_id``."""

    event_type: Literal["foul"] = "foul"
    player_id: Identifier
    opponent_player_id: Identifier
    location: PitchLocation

    @model_validator(mode="after")
    def _check_players(self) -> FoulEvent:
        if self.player_id == self.opponent_player_id:
            raise ValueError("a player cannot foul themselves")
        return self


class RestartType(StrEnum):
    KICKOFF = "kickoff"
    THROW_IN = "throw_in"
    GOAL_KICK = "goal_kick"
    CORNER_KICK = "corner_kick"
    FREE_KICK = "free_kick"


class RestartEvent(_TeamEvent):
    """Play resumes from a dead ball; ``team_id`` takes the restart and holds possession."""

    event_type: Literal["restart"] = "restart"
    restart_type: RestartType
    player_id: Identifier
    location: PitchLocation


class SubstitutionEvent(_TeamEvent):
    event_type: Literal["substitution"] = "substitution"
    player_off_id: Identifier
    player_on_id: Identifier

    @model_validator(mode="after")
    def _check_players(self) -> SubstitutionEvent:
        if self.player_off_id == self.player_on_id:
            raise ValueError("player_on_id must differ from player_off_id")
        return self


class PeriodEndEvent(_EventBase):
    event_type: Literal["period_end"] = "period_end"


MatchEvent = Annotated[
    Union[
        PassEvent,
        ShotEvent,
        TackleEvent,
        PressureEvent,
        InterceptionEvent,
        PossessionChangeEvent,
        FoulEvent,
        RestartEvent,
        SubstitutionEvent,
        PeriodEndEvent,
    ],
    Field(discriminator="event_type"),
]

EventAdapter: TypeAdapter[MatchEvent] = TypeAdapter(MatchEvent)

EVENT_MODELS = (
    PassEvent,
    ShotEvent,
    TackleEvent,
    PressureEvent,
    InterceptionEvent,
    PossessionChangeEvent,
    FoulEvent,
    RestartEvent,
    SubstitutionEvent,
    PeriodEndEvent,
)


class EventSequenceError(ValueError):
    """Raised when a list of events is not a valid chronological match stream."""


def validate_event_sequence(events: Iterable[MatchEvent]) -> Sequence[MatchEvent]:
    """Check stream-level invariants that a single event cannot check on its own.

    - one match_id, unique event_ids
    - strictly increasing ``sequence``
    - time never goes backwards (period, then clock_ms)
    - ``related_event_id`` refers only to an earlier event (no future references)

    Football rules (possession, eligibility, restarts) are checked by
    ``beyond90.schemas.validation.validate_match``.
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
