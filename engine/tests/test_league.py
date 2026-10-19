import hashlib
from pathlib import Path

import pytest

import engine.league
from engine.league import generate_league, is_denied, load_league, save_league
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
    assert not [n for n in names if is_denied(n)]


def test_denylist_matches_on_any_part_of_a_name(monkeypatch: pytest.MonkeyPatch) -> None:
    assert is_denied("Callum Hartley") is False
    hashed = hashlib.sha256(b"hartley").hexdigest()
    monkeypatch.setattr(engine.league, "DENYLIST_SHA256", frozenset({hashed}))
    assert is_denied("Callum Hartley") is True
    assert is_denied("Rhys Pennock") is False


def test_save_and_load_roundtrip(league: League, tmp_path: Path) -> None:
    save_league(league, tmp_path)
    assert load_league(tmp_path) == league
