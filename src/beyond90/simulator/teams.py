"""Fictional teams and squads used by the simulator."""

from __future__ import annotations

from beyond90.schemas import MatchSetup, Player, Position, TeamSheet

GK, DF, MF, FW = Position.GOALKEEPER, Position.DEFENDER, Position.MIDFIELDER, Position.FORWARD

# (shirt, name, position). First 11 start in a 4-3-3; the rest are on the bench.
_SQUADS = {
    ("nbh", "Northbridge Harriers", "NBH"): [
        (1, "Tomas Varrow", GK), (2, "Eli Brandt", DF), (4, "Odran Keel", DF), (5, "Matteo Sorr", DF),
        (3, "Jory Pellan", DF), (6, "Caspian Hale", MF), (8, "Rui Okonde", MF), (10, "Nils Ardent", MF),
        (7, "Dario Quill", FW), (9, "Bram Vettel", FW), (11, "Kofi Marlan", FW),
        (13, "Anders Pike", GK), (15, "Lio Fenner", DF), (16, "Sami Torvik", DF), (14, "Hugo Ressel", MF),
        (18, "Ivo Calder", MF), (20, "Wyn Ostrava", MF), (19, "Pax Deline", FW),
    ],
    ("kes", "Kestrel Bay", "KES"): [
        (1, "Rafe Ondine", GK), (2, "Colm Strand", DF), (4, "Teo Barrigan", DF), (6, "Yusuf Lenk", DF),
        (3, "Ansel Morrow", DF), (5, "Femi Castell", MF), (8, "Lucan Brisk", MF), (10, "Joaquin Vell", MF),
        (7, "Oren Tasker", FW), (9, "Milo Grange", FW), (11, "Sid Harlow", FW),
        (12, "Pieter Gaunt", GK), (15, "Arlo Penn", DF), (17, "Dex Holloway", DF), (14, "Remy Aster", MF),
        (16, "Kai Lunde", MF), (18, "Bastian Crowe", MF), (19, "Zeno Farrell", FW),
    ],
}


def _team_sheet(team_id: str, name: str, short: str, rows) -> TeamSheet:
    squad = tuple(
        Player(player_id=f"{team_id}-{shirt:02d}", name=pname, shirt_number=shirt, position=pos)
        for shirt, pname, pos in rows
    )
    ids = [p.player_id for p in squad]
    return TeamSheet(team_id=team_id, name=name, short_name=short, squad=squad,
                     starting_xi=tuple(ids[:11]), bench=tuple(ids[11:]))


def build_match_setup(match_id: str) -> MatchSetup:
    (home_key, home_rows), (away_key, away_rows) = _SQUADS.items()
    home = _team_sheet(*home_key, home_rows)
    away = _team_sheet(*away_key, away_rows)
    return MatchSetup(match_id=match_id, home=home, away=away,
                      first_half_x105_team_id=home.team_id, first_half_kickoff_team_id=away.team_id)
