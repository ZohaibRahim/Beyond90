import pytest
from pydantic import ValidationError

from beyond90.schemas import MatchSetup, PitchLocation, Position, TeamSheet
from beyond90.simulator.teams import build_match_setup


@pytest.fixture
def setup() -> MatchSetup:
    return build_match_setup("t-001")


def _sheet_data(setup: MatchSetup, **overrides):
    return {**setup.home.model_dump(), **overrides}


def test_fictional_setup_is_valid(setup):
    for team in setup.teams:
        assert len(team.starting_xi) == 11
        assert team.player(team.starting_goalkeeper_id).position is Position.GOALKEEPER
        assert sum(team.player(p).position is Position.GOALKEEPER for p in team.bench) == 1
    assert setup.home.team_id != setup.away.team_id


def test_setup_json_round_trip(setup):
    assert MatchSetup.model_validate_json(setup.model_dump_json()) == setup


def test_xi_needs_exactly_one_goalkeeper(setup):
    bench_gk = next(p for p in setup.home.bench if setup.home.player(p).position is Position.GOALKEEPER)
    two_keepers = (*setup.home.starting_xi[:10], bench_gk)
    two_keepers_bench = tuple(p for p in setup.home.bench if p != bench_gk) + (setup.home.starting_xi[10],)
    with pytest.raises(ValidationError, match="exactly one goalkeeper"):
        TeamSheet.model_validate(_sheet_data(setup, starting_xi=two_keepers, bench=two_keepers_bench))
    no_keeper = (*setup.home.starting_xi[1:], setup.home.bench[-1])
    with pytest.raises(ValidationError, match="exactly one goalkeeper"):
        TeamSheet.model_validate(_sheet_data(setup, starting_xi=no_keeper, bench=setup.home.bench[:-1]))


def test_xi_must_have_eleven(setup):
    with pytest.raises(ValidationError):
        TeamSheet.model_validate(_sheet_data(setup, starting_xi=setup.home.starting_xi[:10]))


def test_lineup_players_must_be_in_squad(setup):
    with pytest.raises(ValidationError, match="not in squad"):
        TeamSheet.model_validate(_sheet_data(setup, bench=(*setup.home.bench, "nobody")))


def test_player_cannot_be_in_xi_and_bench(setup):
    with pytest.raises(ValidationError, match="listed twice"):
        TeamSheet.model_validate(_sheet_data(setup, bench=(*setup.home.bench, setup.home.starting_xi[3])))


def test_duplicate_shirt_numbers_rejected(setup):
    squad = [p.model_dump() for p in setup.home.squad]
    squad[1]["shirt_number"] = squad[0]["shirt_number"]
    with pytest.raises(ValidationError, match="shirt"):
        TeamSheet.model_validate(_sheet_data(setup, squad=squad))


def test_player_ids_unique_across_teams(setup):
    clash = setup.model_dump()
    clash["away"] = {**clash["home"], "team_id": "other"}
    with pytest.raises(ValidationError, match="both teams"):
        MatchSetup.model_validate(clash)


def test_orientation_team_must_exist(setup):
    with pytest.raises(ValidationError):
        MatchSetup.model_validate({**setup.model_dump(), "first_half_x105_team_id": "ghost"})


def test_attacking_direction_swaps_at_halftime(setup):
    home, away = setup.team_ids
    assert setup.attacks_toward_x105(home, 1) and not setup.attacks_toward_x105(home, 2)
    assert not setup.attacks_toward_x105(away, 1) and setup.attacks_toward_x105(away, 2)


def test_attacking_frame_transform(setup):
    home, away = setup.team_ids
    loc = PitchLocation(x=90.0, y=10.0)
    assert setup.to_attacking_frame(loc, home, 1) == loc
    assert setup.to_attacking_frame(loc, home, 2) == PitchLocation(x=15.0, y=58.0)
    assert setup.to_attacking_frame(loc, away, 1) == PitchLocation(x=15.0, y=58.0)
    # Its own inverse.
    assert setup.to_attacking_frame(setup.to_attacking_frame(loc, away, 1), away, 1) == loc


def test_kickoff_alternates_and_player_lookup(setup):
    assert setup.kickoff_team_id(2) == setup.opponent_id(setup.kickoff_team_id(1))
    assert setup.team_of_player(setup.away.starting_xi[0]) == setup.away.team_id
