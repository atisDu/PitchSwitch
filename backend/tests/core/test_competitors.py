"""judge / find_competitors on the fake store with a scripted Gemini judge."""

import pytest

import core.competitors as competitors
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


def judge(picks, space=lambda ids: []):
    """Fake `structured`: records the prompt, answers picks(ids) / space(ids) of candidates."""
    seen = {}

    async def fake(prompt, schema, **kw):
        seen["prompt"] = prompt
        ids = [line.split("id=")[1].split(" |")[0] for line in prompt.splitlines() if "id=" in line]
        seen["ids"] = ids
        cands = ids[1:]  # ids[0] = the startup
        return schema.model_validate({"competitors": picks(cands), "same_space": space(cands)})

    return fake, seen


async def test_keeps_only_candidate_ids_in_judge_order(store, monkeypatch):
    company = await store.company(KELLUU)
    fake, seen = judge(
        lambda ids: [
            {"id": ids[2], "reason": "Also sells aerial surveillance."},
            {"id": "made-up-id", "reason": "invented"},
            {"id": ids[0], "reason": "Same customers."},
            {"id": ids[2], "reason": "duplicate"},
            {"id": KELLUU, "reason": "itself"},
        ]
    )
    monkeypatch.setattr(competitors, "structured", fake)

    out = await competitors.find_competitors(company)

    assert [c.company.id for c in out] == [seen["ids"][3], seen["ids"][1]]
    assert out[0].reason == "Also sells aerial surveillance."
    assert KELLUU not in seen["ids"][1:]  # the startup is never a candidate
    assert all(c.company.sources for c in out)  # candidate Company kept whole, sources included


async def test_caps_at_15(store, monkeypatch):
    company = await store.company(KELLUU)
    many = [company.model_copy(update={"id": f"c{i}"}) for i in range(20)]

    async def candidates(_company, k=30):
        return many

    monkeypatch.setattr(store, "candidate_competitors", candidates)
    fake, _ = judge(lambda ids: [{"id": i, "reason": "r"} for i in ids])
    monkeypatch.setattr(competitors, "structured", fake)

    assert len(await competitors.find_competitors(company)) == 15


async def test_no_candidates_skips_gemini(store, monkeypatch):
    company = (await store.company(KELLUU)).model_copy(update={"id": "unknown"})

    async def boom(*a, **kw):
        raise AssertionError("Gemini called without candidates")

    monkeypatch.setattr(competitors, "structured", boom)
    assert await competitors.find_competitors(company) == []


async def test_same_space_excludes_direct_unknown_and_repeats(store, monkeypatch):
    company = await store.company(KELLUU)
    fake, seen = judge(
        lambda ids: [{"id": ids[0], "reason": "direct"}],
        lambda ids: [ids[0], ids[1], "made-up-id", ids[1], ids[2]],
    )
    monkeypatch.setattr(competitors, "structured", fake)

    out = await competitors.judge(company)

    cands = seen["ids"][1:]
    assert [c.company.id for c in out.direct] == [cands[0]]
    assert [c.id for c in out.space] == [cands[1], cands[2]]


async def test_cached_judge_reuses_until_candidates_change(store, monkeypatch):
    from cache.graph import MemoryGraph

    company = await store.company(KELLUU)
    graph = MemoryGraph()
    fake, seen = judge(lambda ids: [{"id": ids[0], "reason": "direct"}], lambda ids: ids[1:3])
    calls = []

    async def counted(*a, **kw):
        calls.append(1)
        return await fake(*a, **kw)

    monkeypatch.setattr(competitors, "structured", counted)
    first = await competitors.cached_judge(company, graph)
    again = await competitors.cached_judge(company, graph)
    assert again == first and len(calls) == 1
    assert await graph.ids(competitors.JUDGEMENTS) == [f"FakeDataStore:{KELLUU}"]

    real = store.candidate_competitors

    async def fewer(company, k=30):
        return (await real(company, k))[:-1]

    monkeypatch.setattr(store, "candidate_competitors", fewer)
    await competitors.cached_judge(company, graph)
    assert len(calls) == 2  # candidate list changed -> judged again


async def test_cached_judge_survives_a_broken_graph(store, monkeypatch):
    class Broken:
        async def get(self, *a):
            raise ConnectionError("atlas down")

        async def put(self, *a):
            raise ConnectionError("atlas down")

    fake, _ = judge(lambda ids: [{"id": ids[0], "reason": "direct"}])
    monkeypatch.setattr(competitors, "structured", fake)
    out = await competitors.cached_judge(await store.company(KELLUU), Broken())
    assert len(out.direct) == 1
