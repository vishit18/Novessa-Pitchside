import pytest

from engine.league import generate_league
from engine.schema import League
from engine.sim import Match, simulate_match


@pytest.fixture(scope="session")
def league() -> League:
    return generate_league()


@pytest.fixture(scope="session")
def match(league: League) -> Match:
    return simulate_match(league, "ASH", "KES", seed=7, match_id="t01")
