"""Copying the local cache to Atlas: uploads what is missing or newer, never downgrades."""

from cache.atlas import AtlasCache
from cache.files import FileCache
from cache.graph import FileGraph, MemoryGraph
from cache.sync import sync_graph, sync_responses
from tests.cache.test_atlas import FakeCollection


class Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


async def test_responses_keep_their_age_and_newer_remote_copies_win(tmp_path):
    local = FileCache(tmp_path, clock=Clock(1_000.0))
    await local.set("a", {"v": "local a"})
    await local.set("b", {"v": "local b"})
    await local.set("c", {"v": "local c"})
    (tmp_path / "broken.json").write_text("{not json")

    remote = AtlasCache(FakeCollection(), clock=Clock(2_000.0))
    await remote.set("b", {"v": "remote b, newer"})  # stored at 2000
    await remote.set("c", {"v": "remote c, older"}, stored_at=500.0)

    assert await sync_responses(tmp_path, remote) == {"uploaded": 2, "kept": 1}
    assert await remote.get("a") == {"v": "local a"}
    assert await remote.get("b") == {"v": "remote b, newer"}
    assert await remote.get("c") == {"v": "local c"}
    assert await remote.stored_at("a") == 1_000.0  # not "now": it expires when the original would
    assert remote.collection.docs["a"]["expires_at"] == 1_000.0 + 24 * 60 * 60

    assert await sync_responses(tmp_path, remote) == {"uploaded": 0, "kept": 3}
    assert await sync_responses(tmp_path / "missing", remote) == {"uploaded": 0, "kept": 0}


async def test_graph_documents_are_uploaded_unless_the_remote_is_as_new(tmp_path):
    local = FileGraph(tmp_path)
    await local.put("crawl_investors", "tesi", {"name": "Tesi", "crawled_at": 100})
    await local.put("crawl_investors", "maki", {"name": "Maki.vc", "crawled_at": 100})
    await local.put("investor_graph", "tesi", {"co_investors": [], "derived_at": 200})

    remote = MemoryGraph()
    await remote.put("crawl_investors", "maki", {"name": "Maki.vc (remote)", "crawled_at": 150})

    assert await sync_graph(local, remote) == {"uploaded": 2, "kept": 1}
    assert (await remote.get("crawl_investors", "tesi"))["name"] == "Tesi"
    assert (await remote.get("crawl_investors", "maki"))["name"] == "Maki.vc (remote)"
    assert await remote.ids("investor_graph") == ["tesi"]
    assert await sync_graph(local, remote) == {"uploaded": 0, "kept": 3}
    assert await sync_graph(FileGraph(tmp_path / "missing"), remote) == {"uploaded": 0, "kept": 0}
