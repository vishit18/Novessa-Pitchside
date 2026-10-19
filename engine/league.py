"""Fictional league generator. Every name here is invented; keep it that way.

The pools below are deliberately made of uncommon names. Check any new club or
player name against real football before committing it.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from engine.schema import (
    Club,
    League,
    Player,
    PlayerAttributes,
    Position,
    TacticalIdentity,
)

LEAGUE_NAME = "Northbridge League"
DEFAULT_SEED = 2026

# code, name, primary, secondary, ground, label, formation, press, directness, tempo, line
CLUBS = [
    (
        "ASH",
        "Ashford Rovers",
        "#C8372D",
        "#F2EDE4",
        "Millbrook Lane",
        "high press",
        "4-3-3",
        0.85,
        0.45,
        0.8,
        6.0,
    ),
    (
        "KES",
        "Kestrel Bay FC",
        "#1F6FB5",
        "#F5C542",
        "Harbour Road",
        "possession",
        "4-2-3-1",
        0.55,
        0.25,
        0.55,
        3.0,
    ),
    (
        "MIL",
        "Millwater United",
        "#2B8A5A",
        "#FFFFFF",
        "The Weir",
        "direct",
        "4-4-2",
        0.5,
        0.8,
        0.7,
        0.0,
    ),
    (
        "HAR",
        "Harrowgate Athletic",
        "#6B3FA0",
        "#E8E8E8",
        "Crown Fields",
        "deep block",
        "5-4-1",
        0.3,
        0.65,
        0.5,
        -6.0,
    ),
    (
        "POR",
        "Port Calder",
        "#14788C",
        "#F28C28",
        "Quayside Park",
        "possession",
        "4-2-3-1",
        0.6,
        0.3,
        0.6,
        3.0,
    ),
    (
        "RED",
        "Redmoor Town",
        "#8E2A2A",
        "#222222",
        "Heather Ground",
        "direct",
        "4-4-2",
        0.45,
        0.75,
        0.75,
        -1.0,
    ),
    (
        "SAL",
        "Saltmarsh City",
        "#3A3F8F",
        "#DDE6F0",
        "Tidewater Stadium",
        "high press",
        "4-3-3",
        0.8,
        0.5,
        0.85,
        5.0,
    ),
    (
        "THO",
        "Thornbury Wanderers",
        "#B8A02D",
        "#1B1B1B",
        "Bramble Park",
        "deep block",
        "5-4-1",
        0.35,
        0.6,
        0.45,
        -5.0,
    ),
]

FIRST = {
    "English": ["Callum", "Tobias", "Rhys", "Elliot", "Jago", "Finley", "Bertie", "Wilf"],
    "Spanish": ["Iker", "Nacho", "Joaquin", "Tomas", "Dario", "Lucho", "Emilio", "Aitor"],
    "French": ["Remi", "Lucien", "Anselme", "Matteo", "Corentin", "Yanis", "Hugo", "Basile"],
    "Portuguese": ["Duarte", "Rui", "Tiago", "Vasco", "Nuno", "Gil", "Afonso", "Ivo"],
    "Nigerian": ["Chidi", "Tunde", "Obinna", "Femi", "Ikenna", "Kelechi", "Sola", "Dayo"],
    "Indian": ["Arjun", "Rohan", "Vikram", "Kabir", "Dev", "Ishaan", "Neel", "Tarun"],
    "Moroccan": ["Yassine", "Anouar", "Zakaria", "Ilyas", "Hamza", "Mehdi", "Soufiane", "Nabil"],
    "Swedish": ["Anders", "Lasse", "Henrik", "Sixten", "Emil", "Torbjorn", "Viggo", "Ove"],
}
LAST = {
    "English": [
        "Hartley",
        "Pennock",
        "Wragg",
        "Tolliver",
        "Ashdown",
        "Garside",
        "Fenwick",
        "Larkin",
    ],
    "Spanish": [
        "Quiroga",
        "Bermudo",
        "Salcedo",
        "Ledesma",
        "Orbaiz",
        "Cardenal",
        "Vallejo",
        "Tamayo",
    ],
    "French": [
        "Delcourt",
        "Marchetti",
        "Lavigne",
        "Perrault",
        "Soulier",
        "Brocard",
        "Valmont",
        "Ferrand",
    ],
    "Portuguese": [
        "Falcao",
        "Brandao",
        "Nogueira",
        "Rebelo",
        "Tavares",
        "Aguiar",
        "Lacerda",
        "Meireles",
    ],
    "Nigerian": ["Adeyemi", "Okwuosa", "Nwosu", "Balogun", "Egwu", "Ogunlade", "Anyaoku", "Eze"],
    "Indian": ["Bhandari", "Chaudhry", "Rawat", "Iyengar", "Menon", "Sodhi", "Kulkarni", "Talwar"],
    "Moroccan": [
        "Benhaddou",
        "El Fassi",
        "Tazi",
        "Ouazzani",
        "Bennani",
        "Lahlou",
        "Sbai",
        "Chraibi",
    ],
    "Swedish": [
        "Lindqvist",
        "Hedlund",
        "Sjoberg",
        "Ekstrand",
        "Norrby",
        "Falkman",
        "Roslund",
        "Backlund",
    ],
}

# Surnames of well-known players we must never generate. Checked in tests.
DENYLIST = {
    "Saka",
    "Haaland",
    "Salah",
    "Rashford",
    "Foden",
    "Rice",
    "Kane",
    "Bruyne",
    "Son",
    "Fernandes",
    "Odegaard",
    "Palmer",
    "Watkins",
    "Isak",
    "Gordon",
    "Trippier",
    "Pickford",
    "Walker",
    "Stones",
    "Mbeumo",
    "Wirtz",
    "Gakpo",
    "Diaz",
    "Szoboszlai",
    "Alisson",
    "Raya",
    "Saliba",
    "Rodri",
}

# 2 GK, 6 DEF, 6 MID, 4 FWD, with shirt numbers.
SQUAD: list[tuple[Position, list[int]]] = [
    ("GK", [1, 13]),
    ("DEF", [2, 3, 4, 5, 12, 15]),
    ("MID", [6, 8, 10, 14, 16, 18]),
    ("FWD", [7, 9, 11, 17]),
]

# Mean attribute by position group, before club strength and noise.
PROFILE: dict[Position, dict[str, int]] = {
    "GK": dict(
        pace=45,
        acceleration=45,
        stamina=60,
        passing=58,
        vision=55,
        first_touch=50,
        finishing=20,
        shot_power=40,
        tackling=35,
        positioning=72,
        pressing=30,
        composure=65,
    ),
    "DEF": dict(
        pace=62,
        acceleration=60,
        stamina=68,
        passing=60,
        vision=55,
        first_touch=55,
        finishing=35,
        shot_power=52,
        tackling=70,
        positioning=68,
        pressing=62,
        composure=62,
    ),
    "MID": dict(
        pace=64,
        acceleration=64,
        stamina=74,
        passing=72,
        vision=70,
        first_touch=68,
        finishing=55,
        shot_power=64,
        tackling=60,
        positioning=64,
        pressing=66,
        composure=66,
    ),
    "FWD": dict(
        pace=74,
        acceleration=73,
        stamina=66,
        passing=62,
        vision=62,
        first_touch=70,
        finishing=74,
        shot_power=74,
        tackling=36,
        positioning=70,
        pressing=56,
        composure=68,
    ),
}


def _clamp(v: float) -> int:
    return max(1, min(99, round(v)))


def _make_player(
    rng: random.Random, code: str, shirt: int, pos: Position, strength: float, used: set[str]
) -> Player:
    while True:
        nat = rng.choice(list(FIRST))
        name = f"{rng.choice(FIRST[nat])} {rng.choice(LAST[nat])}"
        if name not in used:
            used.add(name)
            break
    attrs = {k: _clamp(m + strength + rng.gauss(0, 7)) for k, m in PROFILE[pos].items()}
    return Player(
        id=f"{code}-{shirt:02d}",
        name=name,
        shirt=shirt,
        position=pos,
        foot="left" if rng.random() < 0.25 else "right",
        age=rng.randint(18, 36),
        nationality=nat,
        attributes=PlayerAttributes(**attrs),
    )


def generate_league(seed: int = DEFAULT_SEED) -> League:
    """Build the eight clubs and their squads from a fixed seed."""
    rng = random.Random(seed)
    used: set[str] = set()
    clubs: list[Club] = []
    for code, name, c1, c2, ground, label, form, press, direct, tempo, line in CLUBS:
        strength = round(rng.uniform(-5, 7), 1)
        players = [
            _make_player(rng, code, n, pos, strength, used) for pos, nums in SQUAD for n in nums
        ]
        clubs.append(
            Club(
                code=code,
                name=name,
                primary_color=c1,
                secondary_color=c2,
                ground=ground,
                strength=strength,
                identity=TacticalIdentity(
                    label=label,
                    formation=form,
                    press=press,
                    directness=direct,
                    tempo=tempo,
                    line_height=line,
                ),
                players=players,
            )
        )
    return League(name=LEAGUE_NAME, seed=seed, clubs=clubs)


def save_league(league: League, directory: Path) -> None:
    """Write clubs.json (without squads) and players.json (all squads) to `directory`."""
    directory.mkdir(parents=True, exist_ok=True)
    meta = {
        "name": league.name,
        "seed": league.seed,
        "clubs": [c.model_dump(exclude={"players"}) for c in league.clubs],
    }
    players = {c.code: [p.model_dump() for p in c.players] for c in league.clubs}
    (directory / "clubs.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (directory / "players.json").write_text(json.dumps(players, indent=2), encoding="utf-8")


def load_league(directory: Path) -> League:
    """Read a league written by `save_league`."""
    meta = json.loads((directory / "clubs.json").read_text(encoding="utf-8"))
    players = json.loads((directory / "players.json").read_text(encoding="utf-8"))
    for club in meta["clubs"]:
        club["players"] = players[club["code"]]
    return League.model_validate(meta)
