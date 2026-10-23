"""Upload the Northbridge League dataset to a Fabric lakehouse, keyless.

    uv run python -m scripts.export_dataset                         # writes data/export/
    uv run python -m fabric.upload_to_onelake --workspace pitchside --lakehouse pitchside

Puts matches.parquet, events.parquet, players.parquet and data/league/clubs.json into
Files/northbridge/ in the lakehouse, where fabric/notebooks/load_northbridge.py reads them.
Uses the ADLS Gen2 API that OneLake speaks, signed in as your `az login` identity (you need
Contributor on the Fabric workspace). Re-running overwrites the files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import quote

import httpx
from azure.identity import DefaultAzureCredential

ROOT = Path(__file__).resolve().parents[1]
ONELAKE = "https://onelake.dfs.fabric.microsoft.com"
STORAGE_SCOPE = "https://storage.azure.com/.default"
API_VERSION = "2023-11-03"
CHUNK = 8 * 1024 * 1024
FOLDER = "Files/northbridge"


def sources(export_dir: Path) -> list[Path]:
    files = [export_dir / f"{n}.parquet" for n in ("matches", "events", "players")]
    files.append(ROOT / "data" / "league" / "clubs.json")
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise SystemExit(f"missing {missing}; run `uv run python -m scripts.export_dataset` first")
    return files


def file_url(workspace: str, lakehouse: str, name: str) -> str:
    item = lakehouse if "." in lakehouse else f"{lakehouse}.Lakehouse"
    return f"{ONELAKE}/{quote(workspace)}/{quote(item)}/{FOLDER}/{quote(name)}"


def upload(client: httpx.Client, url: str, data: bytes) -> None:
    """Create, append in chunks, flush: the ADLS Gen2 way to write a file."""
    # An empty body still needs Content-Length: 0, which content=b"" sends.
    client.put(url, params={"resource": "file"}, content=b"").raise_for_status()
    for pos in range(0, len(data), CHUNK):
        part = data[pos : pos + CHUNK]
        client.patch(
            url, params={"action": "append", "position": pos}, content=part
        ).raise_for_status()
    client.patch(
        url, params={"action": "flush", "position": len(data)}, content=b""
    ).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workspace", required=True, help="Fabric workspace name")
    parser.add_argument("--lakehouse", required=True, help="lakehouse name")
    parser.add_argument("--export-dir", type=Path, default=ROOT / "data" / "export")
    args = parser.parse_args()

    files = sources(args.export_dir)
    token = DefaultAzureCredential().get_token(STORAGE_SCOPE).token
    headers = {"Authorization": f"Bearer {token}", "x-ms-version": API_VERSION}
    with httpx.Client(headers=headers, timeout=120) as client:
        for f in files:
            data = f.read_bytes()
            upload(client, file_url(args.workspace, args.lakehouse, f.name), data)
            print(f"{FOLDER}/{f.name}: {len(data) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
