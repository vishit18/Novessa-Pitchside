import asyncio
from dataclasses import dataclass

from engine.clock import ReplayClock, merge_by_time, stream


@dataclass
class Item:
    t_match: float
    label: str = ""


class Fake:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.t += s


def test_speed_and_pause() -> None:
    f = Fake()
    c = ReplayClock(speed=4.0, now=f.now)
    assert c.match_time() == 0.0
    c.play()
    f.t = 10.0
    assert c.match_time() == 40.0
    c.pause()
    f.t = 50.0
    assert c.match_time() == 40.0
    c.play()
    f.t = 51.0
    assert c.match_time() == 44.0


def test_set_speed_and_seek() -> None:
    f = Fake()
    c = ReplayClock(speed=1.0, now=f.now)
    c.play()
    f.t = 10.0
    c.set_speed(10.0)
    f.t = 12.0
    assert c.match_time() == 30.0
    c.seek(1000.0)
    f.t = 13.0
    assert c.match_time() == 1010.0


def test_stream_emits_in_order_at_speed() -> None:
    f = Fake()
    c = ReplayClock(speed=10.0, now=f.now)
    c.play()
    items = [Item(5.0, "a"), Item(20.0, "b"), Item(100.0, "c")]
    seen: list[tuple[str, float]] = []

    async def run() -> None:
        async for it in stream(items, c, sleep=f.sleep, poll=0.05):
            seen.append((it.label, c.match_time()))

    asyncio.run(run())
    assert [s[0] for s in seen] == ["a", "b", "c"]
    for (label, at), item in zip(seen, items, strict=True):
        assert item.t_match <= at < item.t_match + 1.0, label
    assert f.t < 11.0  # 100 s of match at 10x


def test_stream_skips_items_behind_a_seek() -> None:
    f = Fake()
    c = ReplayClock(speed=10.0, start=50.0, now=f.now)
    c.play()
    out: list[str] = []

    async def run() -> None:
        async for it in stream([Item(10, "old"), Item(60, "new")], c, sleep=f.sleep):
            out.append(it.label)

    asyncio.run(run())
    assert out == ["new"]


def test_merge_by_time() -> None:
    a = [Item(1), Item(4), Item(9)]
    b = [Item(2), Item(3), Item(10)]
    assert [i.t_match for i in merge_by_time(a, b)] == [1, 2, 3, 4, 9, 10]
