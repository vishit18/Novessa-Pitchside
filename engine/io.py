"""Read and write matches on disk.

`<id>.jsonl` holds one meta line then one line per event. The hidden storyline script goes to
`<id>.script.json` so it never travels with the events the agents read. Tracking is not stored:
it regenerates from the seed.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.schema import MatchEvent, MatchMeta
from engine.sim import Match


def write_match(match: Match, directory: Path) -> Path:
    """Write a match to `directory` and return the events file path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{match.meta.match_id}.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"record": "meta", **match.meta.model_dump()}) + "\n")
        for ev in match.events:
            fh.write(ev.model_dump_json(exclude_defaults=True) + "\n")
    script = {"score": list(match.score), "arcs": match.script}
    (directory / f"{match.meta.match_id}.script.json").write_text(
        json.dumps(script, indent=2), encoding="utf-8"
    )
    return path


def read_match_file(path: Path) -> tuple[MatchMeta, list[MatchEvent]]:
    """Read a file written by `write_match`."""
    with path.open(encoding="utf-8") as fh:
        meta_line = json.loads(fh.readline())
        meta_line.pop("record")
        meta = MatchMeta.model_validate(meta_line)
        events = [MatchEvent.model_validate_json(line) for line in fh if line.strip()]
    return meta, events
