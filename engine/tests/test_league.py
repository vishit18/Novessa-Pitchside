from pathlib import Path

from engine.league import DENYLIST, generate_league, load_league, save_league
from engine.schema import League


def test_league_is_deterministic() -> None:
    assert generate_league(5) == generate_league(5)
    assert generate_league(5) != generate_league(6)


def test_squads_and_ids(league: League) -> None:
    assert len(league.clubs) == 8
    ids = [p.id for c in league.clubs for p in c.players]
    assert len(ids) == len(set(ids))
    for club in league.clubs:
        assert len(club.players) == 18
        assert all(p.id.startswith(club.code + "-") for p in club.players)


def test_names_unique_and_not_on_denylist(league: League) -> None:
    names = [p.name for c in league.clubs for p in c.players]
    assert len(names) == len(set(names))
    for n in names:
        assert not set(n.split()) & DENYLIST


def test_save_and_load_roundtrip(league: League, tmp_path: Path) -> None:
    save_league(league, tmp_path)
    assert load_league(tmp_path) == league
