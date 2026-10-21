"""Hand-built streams exercising each football rule in MatchStateTracker."""

import pytest

from beyond90.schemas import MatchValidationError, validate_match
from streams import SETUP, Stream


def opened():
    return Stream().kickoff("kes", "kes-09").pass_("kes", "kes-09", "kes-08")


def fails(builder, match):
    with pytest.raises(MatchValidationError, match=match):
        builder()


def test_complete_mini_match_is_valid_and_scored():
    s = opened()
    s.add("pressure", team_id="nbh", player_id="nbh-09", opponent_player_id="kes-08",
          location={"x": 40, "y": 30}, duration_ms=900)
    s.add("tackle", team_id="nbh", player_id="nbh-09", opponent_player_id="kes-08",
          location={"x": 40, "y": 30}, outcome="won")
    s.add("possession_change", team_id="nbh", previous_team_id="kes", cause="tackle", player_id="nbh-09",
          location={"x": 40, "y": 30}, related_event_id="e0003")
    s.add("shot", team_id="nbh", player_id="nbh-09", location={"x": 95, "y": 34}, outcome="goal",
          body_part="right_foot")
    s.kickoff("kes", "kes-07")
    s.pass_("kes", "kes-07", outcome="out_of_play", end=(60, 68))
    s.add("restart", team_id="nbh", restart_type="throw_in", player_id="nbh-03", location={"x": 60, "y": 68})
    s.end_period(1)
    s.add("substitution", team_id="kes", player_off_id="kes-11", player_on_id="kes-19", clock_ms=0, period=2)
    s.kickoff("nbh", "nbh-09")
    s.end_period(2)
    s.tracker.finish()
    assert s.tracker.score == {"nbh": 1, "kes": 0}
    assert validate_match(SETUP, s.events).score == {"nbh": 1, "kes": 0}


# -- kickoffs, periods, completeness -------------------------------------------

def test_match_must_start_with_kickoff_by_designated_team():
    fails(lambda: Stream().kickoff("nbh", "nbh-09"), "should be taken by kes")
    fails(lambda: Stream().pass_("kes", "kes-09", "kes-08"), "not allowed while ball is dead")


def test_kickoff_must_be_on_centre_spot():
    fails(lambda: Stream().add("restart", team_id="kes", restart_type="kickoff", player_id="kes-09",
                               location={"x": 50, "y": 34}), "centre spot")


def test_period_two_kickoff_by_other_team():
    fails(lambda: opened().end_period(1).kickoff("kes", "kes-09", clock_ms=0, period=2), "should be taken by nbh")


def test_period_must_last_45_minutes():
    fails(lambda: opened().add("period_end", clock_ms=40 * 60_000), "at least 45 minutes")


def test_cannot_skip_to_period_two_without_ending_period_one():
    fails(lambda: opened().kickoff("nbh", "nbh-09", period=2, clock_ms=0), "before period 1 ended")


def test_no_events_after_match_end():
    s = opened().end_period(1).kickoff("nbh", "nbh-09", clock_ms=0, period=2).end_period(2)
    fails(lambda: s.pass_("nbh", "nbh-09", "nbh-08"), "after the end of the match")


def test_incomplete_match_rejected():
    with pytest.raises(MatchValidationError, match="incomplete"):
        validate_match(SETUP, opened().events)


# -- possession continuity -----------------------------------------------------

def test_only_possessing_team_may_pass_or_shoot():
    fails(lambda: opened().pass_("nbh", "nbh-08", "nbh-09"), "kes has possession")
    fails(lambda: opened().add("shot", team_id="nbh", player_id="nbh-09", location={"x": 95, "y": 34},
                               outcome="saved", body_part="head"), "kes has possession")


def test_defensive_actions_only_by_team_without_ball():
    fails(lambda: opened().add("pressure", team_id="kes", player_id="kes-07", opponent_player_id="kes-08",
                               location={"x": 50, "y": 30}, duration_ms=500), "while in possession")


def test_incomplete_pass_must_resolve_with_possession_change():
    s = opened().pass_("kes", "kes-08", outcome="incomplete")
    fails(lambda: s.pass_("kes", "kes-08", "kes-10"), "not allowed while ball is turnover_pending")


def test_possession_change_cause_must_match():
    s = opened().pass_("kes", "kes-08", outcome="incomplete")
    fails(lambda: s.add("possession_change", team_id="nbh", previous_team_id="kes", cause="tackle",
                        location={"x": 55, "y": 30}), "does not match")


def test_possession_change_needs_a_cause_event():
    fails(lambda: opened().add("possession_change", team_id="nbh", previous_team_id="kes",
                               cause="tackle", location={"x": 55, "y": 30}), "ball is in_play")


def test_interception_then_possession_change_is_valid():
    s = opened().pass_("kes", "kes-08", outcome="incomplete")
    s.add("interception", team_id="nbh", player_id="nbh-06", location={"x": 55, "y": 30})
    s.add("possession_change", team_id="nbh", previous_team_id="kes", cause="interception",
          player_id="nbh-06", location={"x": 55, "y": 30})
    s.pass_("nbh", "nbh-06", "nbh-08")


# -- restarts --------------------------------------------------------------------

def test_out_of_play_pass_must_end_on_boundary():
    fails(lambda: opened().pass_("kes", "kes-08", outcome="out_of_play", end=(60, 30)), "boundary")


def test_throw_in_goes_to_other_team_on_touchline():
    s = opened().pass_("kes", "kes-08", outcome="out_of_play", end=(60, 0))
    fails(lambda: s.add("restart", team_id="kes", restart_type="throw_in", player_id="kes-03",
                        location={"x": 60, "y": 0}), "should be taken by nbh")
    s2 = opened().pass_("kes", "kes-08", outcome="out_of_play", end=(60, 0))
    fails(lambda: s2.add("restart", team_id="nbh", restart_type="throw_in", player_id="nbh-03",
                         location={"x": 60, "y": 5}), "touchline")


def test_foul_gives_free_kick_to_fouled_team():
    s = opened().add("foul", team_id="nbh", player_id="nbh-06", opponent_player_id="kes-08",
                     location={"x": 55, "y": 30})
    fails(lambda: s.add("restart", team_id="nbh", restart_type="free_kick", player_id="nbh-06",
                        location={"x": 55, "y": 30}), "should be taken by kes")


def test_goal_requires_kickoff_by_conceding_team():
    s = Stream().kickoff("kes", "kes-09").add("shot", team_id="kes", player_id="kes-09",
                                               location={"x": 10, "y": 34}, outcome="goal", body_part="head")
    fails(lambda: s.kickoff("kes", "kes-07"), "should be taken by nbh")


# -- pitch orientation -------------------------------------------------------------

def test_shot_direction_follows_period():
    # kes attacks toward x=0 in period 1, so a kes shot at x=95 is from its own half.
    fails(lambda: Stream().kickoff("kes", "kes-09").add(
        "shot", team_id="kes", player_id="kes-09", location={"x": 95, "y": 34}, outcome="saved",
        body_part="head"), "own half")


def test_goal_kick_must_be_from_own_goal_area_and_ends_swap():
    def off_target(period_two: bool):
        s = opened()
        if period_two:
            s.end_period(1).kickoff("nbh", "nbh-09", clock_ms=0, period=2).pass_("nbh", "nbh-09", "nbh-08")
            s.add("shot", team_id="nbh", player_id="nbh-08", location={"x": 12, "y": 34},
                  outcome="off_target", body_part="right_foot")
        else:
            s.add("shot", team_id="kes", player_id="kes-08", location={"x": 12, "y": 34},
                  outcome="off_target", body_part="right_foot")
        return s

    # Period 1: nbh defends the x=0 goal.
    off_target(False).add("restart", team_id="nbh", restart_type="goal_kick", player_id="nbh-01",
                          location={"x": 5.0, "y": 34})
    fails(lambda: off_target(False).add("restart", team_id="nbh", restart_type="goal_kick",
                                        player_id="nbh-01", location={"x": 100.0, "y": 34}), "own goal area")
    # Period 2: nbh shot at x=12 is toward x=0, so kes defends x=0.
    off_target(True).add("restart", team_id="kes", restart_type="goal_kick", player_id="kes-01",
                         location={"x": 4.0, "y": 30})


# -- eligibility and substitutions -------------------------------------------------

def test_bench_player_cannot_act():
    fails(lambda: opened().pass_("kes", "kes-08", "kes-19"), "not on the pitch")


def test_opponent_cannot_receive_pass():
    fails(lambda: opened().pass_("kes", "kes-08", "nbh-09"), "not on the pitch for kes")


def dead_ball():
    return opened().pass_("kes", "kes-08", outcome="out_of_play", end=(60, 0))


def test_substitution_only_when_ball_dead():
    fails(lambda: opened().add("substitution", team_id="kes", player_off_id="kes-11", player_on_id="kes-19"),
          "ball is in_play")


def test_substitute_must_be_unused_bench_player():
    s = dead_ball().add("substitution", team_id="kes", player_off_id="kes-11", player_on_id="kes-19")
    fails(lambda: s.add("substitution", team_id="kes", player_off_id="kes-10", player_on_id="kes-11"),
          "not an unused substitute")
    fails(lambda: dead_ball().add("substitution", team_id="kes", player_off_id="kes-19",
                                  player_on_id="kes-18"), "not on the pitch")


def test_substituted_player_cannot_act():
    s = dead_ball().add("substitution", team_id="nbh", player_off_id="nbh-03", player_on_id="nbh-15")
    fails(lambda: s.add("restart", team_id="nbh", restart_type="throw_in", player_id="nbh-03",
                        location={"x": 60, "y": 0}), "not on the pitch")
    s.add("restart", team_id="nbh", restart_type="throw_in", player_id="nbh-15", location={"x": 60, "y": 0})


def test_goalkeeper_replaced_only_by_goalkeeper():
    fails(lambda: dead_ball().add("substitution", team_id="kes", player_off_id="kes-01",
                                  player_on_id="kes-15"), "goalkeeper")
    dead_ball().add("substitution", team_id="kes", player_off_id="kes-01", player_on_id="kes-12")


def test_substitution_limit():
    s = Stream(SETUP.model_copy(update={"max_substitutions": 1}))
    s.kickoff("kes", "kes-09").pass_("kes", "kes-09", outcome="out_of_play", end=(60, 0))
    s.add("substitution", team_id="kes", player_off_id="kes-11", player_on_id="kes-19")
    fails(lambda: s.add("substitution", team_id="kes", player_off_id="kes-10", player_on_id="kes-18"),
          "exceeded 1")
