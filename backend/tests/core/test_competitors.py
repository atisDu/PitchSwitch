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


async def test_cached_judge_judges_each_candidate_once(store, monkeypatch):
    """A changed candidate list only sends its new candidates to Gemini; every earlier verdict is
    kept, even if Gemini would now say otherwise (live: Kelluu's Origin Robotics flipped)."""
    from cache.graph import MemoryGraph

    company = await store.company(KELLUU)
    graph = MemoryGraph()
    real = store.candidate_competitors
    all_ = await real(company, 30)

    async def without_last(company, k=30):
        return all_[:-1]

    monkeypatch.setattr(store, "candidate_competitors", without_last)
    asked = []
    fake, seen = judge(lambda ids: [{"id": ids[0], "reason": "direct"}], lambda ids: ids[1:3])

    async def counted(*a, **kw):
        out = await fake(*a, **kw)
        asked.append(seen["ids"][1:])
        return out

    monkeypatch.setattr(competitors, "structured", counted)
    first = await competitors.cached_judge(company, graph)
    assert await competitors.cached_judge(company, graph) == first and len(asked) == 1

    monkeypatch.setattr(store, "candidate_competitors", real)  # one new candidate comes in
    later = await competitors.cached_judge(company, graph)
    assert asked[1] == [all_[-1].id]  # only the new one was judged
    assert later.direct[0] == first.direct[0]  # and it was judged direct, after the first
    assert [c.company.id for c in later.direct] == [first.direct[0].company.id, all_[-1].id]

    monkeypatch.setattr(store, "candidate_competitors", without_last)  # it drops out again
    assert await competitors.cached_judge(company, graph) == first and len(asked) == 2


async def test_cached_judge_takes_over_the_judgements_stored_per_candidate_list(
    store, monkeypatch
):
    """No Gemini call for what was judged before; where old docs disagree, the one for today's
    candidate list wins, then the oldest."""
    from cache.graph import MemoryGraph

    company = await store.company(KELLUU)
    cands = [c for c in await store.candidate_competitors(company, 30) if c.id != KELLUU]
    a, b = cands[0], cands[1]
    now = sorted(c.id for c in cands)

    def doc(direct, ids):
        judged = competitors.Judgement(
            direct=[competitors.Competitor(company=c, reason="r") for c in direct], space=[]
        )
        return {"candidates": ids, "judgement": judged.model_dump(mode="json")}

    graph = MemoryGraph()
    await graph.put(competitors.JUDGEMENTS, f"FakeDataStore:{KELLUU}", doc([a, b], now[:-1]))
    await graph.put(competitors.JUDGEMENTS, f"FakeDataStore:{KELLUU}:abc", doc([a], now))

    async def never(*a, **kw):
        raise AssertionError("judged again")

    monkeypatch.setattr(competitors, "structured", never)
    out = await competitors.cached_judge(company, graph)
    assert [c.company.id for c in out.direct] == [a.id]  # today's list says b is not direct
    assert await graph.get(competitors.VERDICTS, f"FakeDataStore:{KELLUU}")  # migrated once


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
