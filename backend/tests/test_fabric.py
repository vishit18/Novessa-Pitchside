"""Fabric artefacts: the KQL stays in step with the league, the notebook SQL adds up, and the
OneLake upload speaks ADLS Gen2."""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path

import httpx
import pytest

from engine.league import load_league
from fabric import upload_to_onelake
from fabric.build_reference import OUT, reference_kql
from scripts.export_dataset import one_match

ROOT = Path(__file__).resolve().parents[2]
KQL = ROOT / "fabric" / "kql"
NOTEBOOK = ROOT / "fabric" / "notebooks" / "load_northbridge.py"


def test_reference_kql_matches_the_league() -> None:
    assert OUT.read_text("utf-8") == reference_kql(load_league(ROOT / "data" / "league"))


def _defined(text: str) -> set[str]:
    return set(re.findall(r"^\.create-or-alter function[^\n]*\n(\w+)\(", text, flags=re.M))


def test_every_dashboard_tile_uses_a_defined_function() -> None:
    defined = set()
    for f in ("00_reference.kql", "01_tables.kql", "02_functions.kql"):
        defined |= _defined((KQL / f).read_text("utf-8"))
    assert {"Clubs", "Players", "ExpandEvents", "ExpandBall", "Score", "XgRace"} <= defined
    tiles = (KQL / "03_dashboard.kql").read_text("utf-8")
    used = set(re.findall(r"^(\w+)\(_match\)", tiles, flags=re.M))
    assert used and used <= defined


def test_the_mapping_covers_every_envelope_field() -> None:
    from backend.bus.base import Envelope

    tables = (KQL / "01_tables.kql").read_text("utf-8")
    for field in Envelope.model_fields:
        assert f'"path": "$.{field}"' in tables


def _sql(name: str) -> str:
    tree = ast.parse(NOTEBOOK.read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return str(ast.literal_eval(node.value))
    raise KeyError(name)


@pytest.fixture(scope="module")
def lake() -> sqlite3.Connection:
    """Two exported matches in SQLite, run through the notebook's SQL."""
    db = sqlite3.connect(":memory:")
    rows = [one_match(i) for i in (0, 1)]
    match_cols = list(rows[0][0])
    event_cols = list(rows[0][1][0])
    db.execute(f"CREATE TABLE matches ({', '.join(match_cols)})")
    db.execute(f"CREATE TABLE events ({', '.join(event_cols)})")
    for match, events in rows:
        db.execute(
            f"INSERT INTO matches VALUES ({', '.join('?' * len(match_cols))})", list(match.values())
        )
        db.executemany(
            f"INSERT INTO events VALUES ({', '.join('?' * len(event_cols))})",
            [list(e.values()) for e in events],
        )
    db.execute(f"CREATE TABLE team_match AS {_sql('TEAM_MATCH_SQL')}")
    return db


def test_team_match_adds_up(lake: sqlite3.Connection) -> None:
    rows = lake.execute(
        "SELECT match_id, team, goals_for, goals_against, points, pass_share_pct, shots, xg "
        "FROM team_match"
    ).fetchall()
    assert len(rows) == 4
    for mid, home, away, hg, ag in lake.execute(
        "SELECT match_id, home, away, home_goals, away_goals FROM matches"
    ):
        sides = {r[1]: r for r in rows if r[0] == mid}
        assert sides[home][2:4] == (hg, ag) and sides[away][2:4] == (ag, hg)
        assert sides[home][4] + sides[away][4] in (2, 3)
        assert abs(sides[home][5] + sides[away][5] - 100) <= 0.2
        goals = lake.execute(
            "SELECT team, COUNT(*) FROM events WHERE match_id = ? AND type = 'goal' GROUP BY team",
            (mid,),
        ).fetchall()
        assert dict(goals) == {t: g for t, g in ((home, hg), (away, ag)) if g}
    assert all(r[6] > 0 and r[7] > 0 for r in rows)


def test_league_table(lake: sqlite3.Connection) -> None:
    table = lake.execute(_sql("LEAGUE_TABLE_SQL")).fetchall()
    played = sum(r[1] for r in table)
    assert played == 4
    assert sum(r[7] for r in table) == 0  # goal difference sums to zero


def test_upload_creates_appends_and_flushes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upload_to_onelake, "CHUNK", 4)
    seen: list[tuple[str, str, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        what = params.get("resource") or params["action"]
        seen.append((request.method, what, int(params.get("position", -1))))
        assert request.headers["content-length"] == str(len(request.content))
        return httpx.Response(201 if request.method == "PUT" else 202)

    url = upload_to_onelake.file_url("pitchside", "pitchside", "clubs.json")
    assert url == (
        "https://onelake.dfs.fabric.microsoft.com/pitchside/pitchside.Lakehouse/"
        "Files/northbridge/clubs.json"
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        upload_to_onelake.upload(client, url, b"0123456789")
    assert seen == [
        ("PUT", "file", -1),
        ("PATCH", "append", 0),
        ("PATCH", "append", 4),
        ("PATCH", "append", 8),
        ("PATCH", "flush", 10),
    ]
