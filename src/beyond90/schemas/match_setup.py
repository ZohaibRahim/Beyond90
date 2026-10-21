"""Public roster, lineup and pitch-orientation schema.

Team sheets are announced before kickoff, so they are observable and safe for
the live system. Orientation helpers turn the fixed event coordinates into a
team-relative attacking frame, accounting for the switch of ends at halftime.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from beyond90.schemas.events import PITCH_LENGTH_M, PITCH_WIDTH_M, Identifier, PitchLocation, _Frozen

SETUP_SCHEMA_VERSION = "1.0.0"


class Position(StrEnum):
    GOALKEEPER = "GK"
    DEFENDER = "DF"
    MIDFIELDER = "MF"
    FORWARD = "FW"


class Player(_Frozen):
    player_id: Identifier
    name: str = Field(min_length=1, max_length=80)
    shirt_number: int = Field(ge=1, le=99)
    position: Position


class TeamSheet(_Frozen):
    team_id: Identifier
    name: str = Field(min_length=1, max_length=80)
    short_name: str = Field(min_length=2, max_length=4)
    squad: tuple[Player, ...] = Field(min_length=11, max_length=26)
    starting_xi: tuple[Identifier, ...] = Field(min_length=11, max_length=11)
    bench: tuple[Identifier, ...] = Field(default=(), max_length=15)

    @model_validator(mode="after")
    def _check_sheet(self) -> TeamSheet:
        ids = [p.player_id for p in self.squad]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.team_id}: duplicate player_id in squad")
        shirts = [p.shirt_number for p in self.squad]
        if len(shirts) != len(set(shirts)):
            raise ValueError(f"{self.team_id}: duplicate shirt number")
        listed = list(self.starting_xi) + list(self.bench)
        if len(listed) != len(set(listed)):
            raise ValueError(f"{self.team_id}: a player is listed twice in starting_xi/bench")
        unknown = set(listed) - set(ids)
        if unknown:
            raise ValueError(f"{self.team_id}: players not in squad: {sorted(unknown)}")
        keepers = [p for p in self.starting_xi if self.player(p).position is Position.GOALKEEPER]
        if len(keepers) != 1:
            raise ValueError(f"{self.team_id}: starting_xi must contain exactly one goalkeeper")
        return self

    def player(self, player_id: str) -> Player:
        for p in self.squad:
            if p.player_id == player_id:
                return p
        raise KeyError(player_id)

    @property
    def starting_goalkeeper_id(self) -> str:
        return next(p for p in self.starting_xi if self.player(p).position is Position.GOALKEEPER)


class MatchSetup(_Frozen):
    schema_version: Literal["1.0.0"] = SETUP_SCHEMA_VERSION
    match_id: Identifier
    home: TeamSheet
    away: TeamSheet
    first_half_x105_team_id: Identifier = Field(
        description="Team attacking toward x = 105 in period 1 (ends swap in period 2)."
    )
    first_half_kickoff_team_id: Identifier
    max_substitutions: int = Field(default=5, ge=0, le=5)

    @model_validator(mode="after")
    def _check_setup(self) -> MatchSetup:
        if self.home.team_id == self.away.team_id:
            raise ValueError("home and away must be different teams")
        shared = {p.player_id for p in self.home.squad} & {p.player_id for p in self.away.squad}
        if shared:
            raise ValueError(f"player_id used by both teams: {sorted(shared)}")
        for field in ("first_half_x105_team_id", "first_half_kickoff_team_id"):
            if getattr(self, field) not in self.team_ids:
                raise ValueError(f"{field} must be one of the two teams")
        return self

    @property
    def team_ids(self) -> tuple[str, str]:
        return (self.home.team_id, self.away.team_id)

    @property
    def teams(self) -> tuple[TeamSheet, TeamSheet]:
        return (self.home, self.away)

    def team(self, team_id: str) -> TeamSheet:
        for t in self.teams:
            if t.team_id == team_id:
                return t
        raise KeyError(team_id)

    def opponent_id(self, team_id: str) -> str:
        home, away = self.team_ids
        if team_id == home:
            return away
        if team_id == away:
            return home
        raise KeyError(team_id)

    def team_of_player(self, player_id: str) -> str:
        for t in self.teams:
            if any(p.player_id == player_id for p in t.squad):
                return t.team_id
        raise KeyError(player_id)

    def kickoff_team_id(self, period: int) -> str:
        first = self.first_half_kickoff_team_id
        return first if period == 1 else self.opponent_id(first)

    def attacks_toward_x105(self, team_id: str, period: int) -> bool:
        first = team_id == self.first_half_x105_team_id
        if team_id not in self.team_ids:
            raise KeyError(team_id)
        return first if period == 1 else not first

    def to_attacking_frame(self, location: PitchLocation, team_id: str, period: int) -> PitchLocation:
        """Fixed pitch coordinates -> frame where ``team_id`` attacks toward x = 105.

        The transform is a 180-degree rotation, so it is its own inverse and also
        converts attacking-frame coordinates back to fixed coordinates.
        """
        if self.attacks_toward_x105(team_id, period):
            return location
        return PitchLocation(x=PITCH_LENGTH_M - location.x, y=PITCH_WIDTH_M - location.y)
