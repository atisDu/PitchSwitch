"""B22 portfolio X-ray on the fake store with a scripted Gemini (no network)."""

from datetime import date

import pytest

import core.competitors as competitors
import core.xray as xray
from cache.graph import MemoryGraph
from contracts.schemas import EntityRef, PortfolioLink
from core.scoring import rank_investors
from data import NotFound, get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
TODAY = date(2026, 11, 13)
REAL_VERDICTS = competitors.portfolio_verdicts
REF = {"id", "name", "type", "description"}


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


def scripted(screen_direct=(), screen_space=(), direct=(), space=(), fail_screen=False):
    """Fake `structured`: the name screen flags `screen_*`; the confirm judge (the regular judge
    prompt) calls `direct` direct and `space` same space. Records every call."""
    calls = []

    async def fake(prompt, schema, **kw):
        ids = [line.split("id=")[1].split(" |")[0] for line in prompt.splitlines() if "id=" in line]
        calls.append((schema.__name__, ids[1:]))
        if schema.__name__ == "_Screen":
            if fail_screen:
                raise RuntimeError("Gemini down")
            return schema.model_validate(
                {
                    "direct": [i for i in ids if i in screen_direct],
                    "same_space": [i for i in ids if i in screen_space],
                }
            )
        return schema.model_validate(
            {
                "competitors": [{"id": i, "reason": "Same product."} for i in ids if i in direct],
                "same_space": [i for i in ids if i in space],
            }
        )

    return fake, calls


async def _portfolio_refs(store, n=4) -> list[EntityRef]:
    """Portfolio companies of Kelluu's Pitch investors that the fake store can fetch whole."""
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    report = await rank_investors(company, [], space, today=TODAY)
    refs: dict[str, EntityRef] = {}
    for s in report.pitch:
        for link in await store.portfolio(s.investor.id):
            try:
                await store.company(link.company.id)
            except NotFound:
                continue
            refs.setdefault(link.company.id, link.company)
            if len(refs) == n:
                return list(refs.values())
    pytest.fail(f"fixture: fewer than {n} fetchable portfolio companies")


async def test_screen_then_confirm_and_store_once(store, monkeypatch):
    company = await store.company(KELLUU)
    a, b, c, d = await _portfolio_refs(store)
    fake, calls = scripted(
        screen_direct={a.id}, screen_space={b.id, c.id}, direct={a.id}, space={b.id}
    )
    monkeypatch.setattr(competitors, "structured", fake)
    graph = MemoryGraph()

    got = await REAL_VERDICTS(company, [a, b, c, d], graph)

    assert got[a.id]["tier"] == "direct" and got[a.id]["reason"] == "Same product."
    assert got[b.id]["tier"] == "space"
    assert got[c.id] == {"tier": "unrelated", "by": "portfolio"}  # flagged, not confirmed
    assert got[d.id] == {"tier": "unrelated", "by": "name"}  # never flagged
    assert [name for name, _ in calls] == ["_Screen", "_Judgement"]
    assert set(calls[1][1]) == {a.id, b.id, c.id}  # only the flagged ones are confirmed

    competitors._verdict_memo.clear()  # another process: read back from the graph
    assert await REAL_VERDICTS(company, [a, b, c, d], graph) == got
    assert len(calls) == 2  # judged once, ever


async def test_failed_screen_is_not_stored_and_never_fails(store, monkeypatch):
    company = await store.company(KELLUU)
    refs = await _portfolio_refs(store, 2)
    fake, calls = scripted(fail_screen=True)
    monkeypatch.setattr(competitors, "structured", fake)
    graph = MemoryGraph()
    assert await REAL_VERDICTS(company, refs, graph) == {}
    assert await REAL_VERDICTS(company, refs, graph) == {}
    assert len(calls) == 2  # tried again


async def test_a_candidate_screened_by_name_only_is_judged_properly(store, monkeypatch):
    """The screen's name-only "unrelated" never stands in for the judge's verdict on a
    candidate, and the full verdict replaces it in storage."""
    company = await store.company(KELLUU)
    graph = MemoryGraph()
    cands = [c for c in await store.candidate_competitors(company, 30) if c.id != KELLUU]
    first = cands[0]
    doc = competitors._doc_id(company)
    await graph.put(
        competitors.VERDICTS, doc, {"verdicts": {first.id: {"tier": "unrelated", "by": "name"}}}
    )
    fake, calls = scripted(direct={first.id})
    monkeypatch.setattr(competitors, "structured", fake)

    judged = await competitors.cached_judge(company, graph)

    assert first.id in calls[0][1]
    assert judged.direct[0].company.id == first.id
    stored = (await graph.get(competitors.VERDICTS, doc))["verdicts"][first.id]
    assert stored["tier"] == "direct" and "by" not in stored


async def test_report_moves_a_hidden_rival_backer_to_skip_and_counts_the_thesis(store, monkeypatch):
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    base = await rank_investors(company, [], space, today=TODAY)
    listed = {company.id, *(c.id for c in space)}
    target = None
    for s in base.pitch:  # a Pitch investor holding two companies off the report
        off = [lk for lk in await store.portfolio(s.investor.id) if lk.company.id not in listed]
        if len(off) >= 2:
            target, (rival, peer) = s, off[:2]
            break
    assert target is not None, "fixture: no Pitch investor with two companies off the report"

    async def verdicts(company, refs, graph=None):
        tiers = {
            rival.company.id: {"tier": "direct", "reason": "Same customers."},
            peer.company.id: {"tier": "space"},
        }
        return {r.id: tiers[r.id] for r in refs if r.id in tiers}

    monkeypatch.setattr(xray, "portfolio_verdicts", verdicts)
    after = await rank_investors(company, [], space, today=TODAY, xray=True)

    skipped = {s.investor.id: s for s in after.skip}
    assert target.investor.id in skipped and target.investor.id not in {
        s.investor.id for s in after.pitch
    }
    s = skipped[target.investor.id]
    assert [c.competitor.id for c in s.conflicts] == [rival.company.id]
    assert s.conflicts[0].kind == "PORTFOLIO" and s.conflicts[0].sources == rival.sources
    assert s.reasons[0].text.startswith("Score ")  # the breakdown stays first (C17 parses it)
    hidden = [r for r in s.reasons if r.text.startswith("Hidden conflict:")]
    assert len(hidden) == 1 and rival.company.name in hidden[0].text
    assert "not on your competitor list" in hidden[0].text
    thesis = [r for r in s.reasons if r.text.startswith("Its portfolio holds 1 company")]
    assert thesis and peer.company.name in thesis[0].text
    assert "only in its portfolio, counted half" in s.reasons[0].text


async def test_listed_companies_are_never_hidden_rivals(store, monkeypatch):
    """A company on the report (the judge's rivals, also one the user removed, and the space) is
    never a hidden rival, whatever its verdict."""
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    links = [
        PortfolioLink(investor_id="inv", company=EntityRef(**c.model_dump(include=REF)))
        for c in space[:3]
    ]

    async def everything_direct(company, refs, graph=None):
        return {r.id: {"tier": "direct", "reason": "r"} for r in refs}

    monkeypatch.setattr(xray, "portfolio_verdicts", everything_direct)
    out = await xray.xray(company, {"inv": links}, {company.id, *(c.id for c in space)})
    assert out["inv"].hidden == [] and out["inv"].thesis == []

    off = await xray.xray(company, {"inv": links}, {company.id})  # not listed: all three hidden
    assert [c.company.id for c in off["inv"].hidden] == [c.id for c in space[:3]]
    assert all(c.reason.endswith("(not on your competitor list)") for c in off["inv"].hidden)
