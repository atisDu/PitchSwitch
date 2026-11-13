"""FileCache: the same rules as the Atlas cache, on local files."""

from cache.files import FileCache


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


async def test_round_trip_expiry_and_stale(tmp_path):
    clock = Clock()
    cache = FileCache(tmp_path / "cala", clock=clock)
    value = {"name": "Kelluu Oy", "nested": {"a.b": [1, 2.5, None, "ö"]}}
    assert await cache.get("POST /entities/x#1") is None
    assert await cache.count() == {"total": 0, "fresh": 0, "stale": 0}

    await cache.set("POST /entities/x#1", value)
    await cache.set("POST /entities/x#2", {"other": True})
    assert await cache.get("POST /entities/x#1") == value
    assert await cache.get("POST /entities/x#2") == {"other": True}

    clock.now += 24 * 60 * 60 + 1
    assert await cache.get("POST /entities/x#1") is None
    assert await cache.get_stale("POST /entities/x#1") == value
    assert await cache.count() == {"total": 2, "fresh": 0, "stale": 2}

    await cache.set("POST /entities/x#1", {"v": 2})
    assert await cache.get("POST /entities/x#1") == {"v": 2}
    assert not list((tmp_path / "cala").glob("*.tmp"))


async def test_a_damaged_file_is_a_miss(tmp_path):
    cache = FileCache(tmp_path)
    await cache.set("k", {"v": 1})
    next(tmp_path.glob("*.json")).write_text("{not json")
    assert await cache.get("k") is None and await cache.get_stale("k") is None


async def test_a_second_instance_sees_what_the_first_stored(tmp_path):
    await FileCache(tmp_path).set("k", {"v": 1})
    assert await FileCache(tmp_path).get("k") == {"v": 1}
