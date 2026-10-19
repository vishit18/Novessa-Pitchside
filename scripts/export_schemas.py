"""Write the overlay protocol JSON Schema from the Pydantic models.

uv run python -m scripts.export_schemas
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.overlay import Overlay

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "app" / "schemas" / "overlay.schema.json"


def main() -> None:
    schema = Overlay.model_json_schema()
    schema["$id"] = "https://novessa-pitchside.example/schemas/overlay-v1.json"
    schema["title"] = "Overlay (protocol v1)"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
