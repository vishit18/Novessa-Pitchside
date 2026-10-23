"""Real footage routes: listing, overlay data, and that a clip id cannot leave data/real."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app

CLIP = "117093_w1890"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


def test_clips_are_listed_with_their_validation_numbers(client: TestClient) -> None:
    clips = client.get("/real").json()
    assert [c["clip"] for c in clips] == [CLIP]
    c = clips[0]
    assert c["meta"]["credit"] == "Footage: SoccerTrack v2 (CC BY 4.0)"
    assert {"positions", "speed", "passes", "shots"} <= c["results"].keys()
    assert isinstance(c["video"], bool)


def test_overlay_data_is_vision_only_and_has_frames(client: TestClient) -> None:
    o = client.get(f"/real/{CLIP}/overlay").json()
    assert o["fps"] == 25 and o["clip"] == [2560, 676]
    assert o["frames"] and o["tracks"]
    assert o["events"] and all(e["source"] == "vision" for e in o["events"])
    assert all(t["team"] in ("BLU", "WHT") for t in o["tracks"].values())


def test_the_video_is_404_when_this_server_does_not_have_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("REAL_FOOTAGE_DIR", str(tmp_path))
    monkeypatch.delenv("REAL_VIDEO_BASE_URL", raising=False)
    assert client.get(f"/real/{CLIP}/video").status_code == 404
    (tmp_path / CLIP).mkdir()
    (tmp_path / CLIP / "clip.mp4").write_bytes(b"not really a video")
    ok = client.get(f"/real/{CLIP}/video")
    assert ok.status_code == 200 and ok.headers["content-type"] == "video/mp4"


def test_the_video_redirects_to_blob_when_a_base_url_is_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("REAL_FOOTAGE_DIR", str(tmp_path))
    monkeypatch.setenv("REAL_VIDEO_BASE_URL", "https://example.blob.core.windows.net/footage/")
    r = client.get(f"/real/{CLIP}/video", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == f"https://example.blob.core.windows.net/footage/{CLIP}/clip.mp4"
    assert client.get("/real").json()[0]["video"] is True


@pytest.mark.parametrize("bad", ["..", "..%2F..%2Fetc", "117093_w1890/../x", "nope", "1_w1"])
def test_a_clip_id_cannot_escape_the_data_folder(client: TestClient, bad: str) -> None:
    assert client.get(f"/real/{bad}/overlay").status_code == 404
    assert client.get(f"/real/{bad}/video").status_code == 404
