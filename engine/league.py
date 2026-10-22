"""Fictional league generator. Every name here is invented; keep it that way.

The pools below are deliberately made of uncommon names. Check any new club or
player name against real football before committing it.
"""

from __future__ import annotations

import hashlib
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

# Spare surnames, used only to give team-mates who drew the same surname different ones. Kept
# apart from LAST because the squads draw from LAST, and growing it would change every squad.
LAST_EXTRA = {
    "English": ["Thornbury", "Pellow", "Calloway", "Bramwell", "Whitlock", "Ashcombe", "Fairley",
                "Hensby", "Dunstall", "Selwood", "Quarrie", "Brackley"],
    "Spanish": ["Olabarri", "Villarroel", "Cardenal", "Baquedano", "Irizar", "Lacunza", "Echave",
                "Mendiburu", "Ozores", "Galdeano", "Urquiza", "Basterra"],
    "French": ["Delorme", "Fauvel", "Brissac", "Vauclair", "Tessier", "Lemarque", "Ferrand",
               "Morvan", "Chalaux", "Duvernoy", "Garrigue", "Pellerin"],
    "Portuguese": ["Valadares", "Bettencourt", "Loureiro", "Calheiros", "Mascarenhas", "Arruda",
                   "Vilaca", "Gouveia", "Rebelo", "Sarmento", "Tavira", "Fontoura"],
    "Nigerian": ["Adebanjo", "Olatunji", "Ezeogu", "Akinwale", "Obiefuna", "Oyelaran", "Nnadozie",
                 "Anozie", "Odukoya", "Ajibola", "Okwuosa", "Adeyinka"],
    "Indian": ["Bhandari", "Rathore", "Kamath", "Deshpande", "Iyengar", "Mahajan", "Thakkar",
               "Venkatesh", "Saxena", "Joglekar", "Chaturvedi", "Raghavan"],
    "Moroccan": ["Bennani", "Lamrani", "Chraibi", "Alaoui", "Benjelloun", "Fassi", "Sqalli",
                 "Kettani", "Berrada", "Zniber", "Lahrichi", "Guessous"],
    "Swedish": ["Hedqvist", "Aronsson", "Wallgren", "Kjellberg", "Dahlstrom", "Hagstrom", "Edfelt",
                "Bergkvist", "Ljungdahl", "Tornqvist", "Bladh", "Sandahl"],
}  # fmt: skip

# SHA-256 of lowercased surnames of well-known real players, so none appear in source.
# Generated names are checked against this in tests via `is_denied`.
DENYLIST_SHA256 = frozenset(
    {
        "00a722708a42f2462e1bbdce8d6967d918b4d6e5daafa9fb8a46ddf69a0ae342",
        "0422d5b3a69178aef5290bbe631e2e1bf409931f920f2806d805d04aa85215ad",
        "055654e9d79b0bfaf0532c668e6b03c11677a6c060b1fdbc94f14f5a83cda574",
        "08614c84a3bbb4b05eeea6030fee50ab3baa8475450a5aba9873c04b7cd96feb",
        "1491b1be53d40a5c7365bedfd07f3df08769208dd76356884814f54a328f2339",
        "1a2e90d2c67a115ac9ead4969354337dade76079542aa789953e39a73a0059a9",
        "209f76418ece7c936b65ff4777a578d860f762c37ad6c7f08f5826242199ef51",
        "2101348579746d02ed47ce392c4ed67bafff06f86eddf6663e99d83d65977bea",
        "2d2d674c7150952fb81f5e1f8113c2d32e6167d2c567b3048d3b513a8b79c80f",
        "33db7a9acd9930641bd9dd22a367ac6e2b5f984feeb2b6ab5773794d6fc26854",
        "4d08ae5378638d7eca766c5ab1a4a27220926a02e3c5b6ba97d8e1d4fb0c998a",
        "5b6551cb55a20460e8a97126887e1502a11423a2279f7271502c8017c46290fa",
        "7da426bb0cc1b8e3c0723c900755e5469db12fb840f4f094f07d290696e57cac",
        "8cf25a00956fea6d3a84d53d3a3e291c7183e9c5eaf9425cd36f58311e1d8f84",
        "98aa6675482552881925fe70d82559692d811b3bcd33f53b9a702c24d5322696",
        "9fe93417853739c1c18c2e8b051860d1a317824f1aa91304d16f3fe832486f7a",
        "a5cca33940ed2a85586687cc285e840acd8c5104a9d3887497d0b749a54d943c",
        "baebd585e1b908373adbfb13179c3f969c276e96e47fceecfb56c10f8d11616c",
        "c1dbd67f9e1d046391ba9774bf33792d9c048644b7561f85f6ca74f8449f083c",
        "c4ab1bdd755151aa4a3b53a597f5532e4011c0a4e074c262a58f026d1c183dc8",
        "d3e450cd37f7785cb23dfcef8a37f0df0e719302a73c36931952e2cda2b1677e",
        "d8b01b2435a39d18015cabdf20afba9ca275412f2eb117f80fb7989c4101c029",
        "e675137ec2f19377e04ef495f415108ec3953cd98df03792be0145a559431d6b",
        "ec3620470529f11448cb4ec5baeec3dc4395f58d69d5b99ce1891409a7c02ef7",
        "f57dbb83bc838bda3c0cf7d6091e9a3c16f824cef7ebef8faad554bf5ebc7ad4",
        "f652588e2e7c40029ba044fc9fd660f506a6eb50522c0959cf2b5fef41eba355",
        "f8b003e0b309fd38ca34d66152b3f66a8bd7851166688a810ef51563b1140a65",
        "fcecca0fd203a501524e79667d348fbba752b076db039aabbef646aaff01dabd",
    }
)


def is_denied(full_name: str) -> bool:
    """True if any part of `full_name` matches a denylisted real surname."""
    return any(
        hashlib.sha256(part.lower().encode()).hexdigest() in DENYLIST_SHA256
        for part in full_name.split()
    )


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


def _manager_names(seed: int, taken: set[str]) -> list[str]:
    """Invented manager names. Own generator, so adding managers never changes the squads."""
    rng = random.Random(seed * 7919 + 13)
    names: list[str] = []
    while len(names) < len(CLUBS):
        nat = rng.choice(list(FIRST))
        name = f"{rng.choice(FIRST[nat])} {rng.choice(LAST[nat])}"
        if name not in taken and name not in names and not is_denied(name):
            names.append(name)
    return names


def _unique_surnames(clubs: list[Club], seed: int) -> None:
    """No two team-mates share a surname: a squad with three Garsides reads as a bug.

    The player drawn last keeps a shared surname; the others get a new one from their own
    nationality's pool that no one in the league has. Runs on its own random stream after the
    squads are drawn, so ratings, kits, managers and every match stay exactly as they were.
    """
    rng = random.Random(seed * 104729 + 7)
    taken = {p.name.split()[-1] for c in clubs for p in c.players}
    for club in clubs:
        seen: set[str] = set()
        for p in reversed(club.players):
            first, last = p.name.rsplit(" ", 1)
            if last in seen:
                pool = sorted(
                    s
                    for s in LAST[p.nationality] + LAST_EXTRA[p.nationality]
                    if s not in taken and not is_denied(f"{first} {s}")
                )
                if not pool:
                    raise ValueError(f"no surname left for {p.id} ({p.nationality})")
                last = rng.choice(pool)
                taken.add(last)
                p.name = f"{first} {last}"
            seen.add(last)


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
    _unique_surnames(clubs, seed)
    for club, manager in zip(clubs, _manager_names(seed, used), strict=True):
        club.manager = manager
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
