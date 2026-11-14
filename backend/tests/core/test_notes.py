"""B24 report notes (grants won, at Slush 2026) with scripted Cala search and Gemini."""

from datetime import date

import pytest

import core.fresh as fresh
import core.notes as notes
import core.scoring as scoring
from contracts.schemas import Competitor, Reason, Source
from core.scoring import rank_investors
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
TODAY = date(2026, 11, 13)
SRC = Source(name="DIANA", url="https://diana.nato.int/x", rank="PRIMARY")
REAL_NOTES = notes.report_notes


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


async def rivals(store):
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    return company, [Competitor(company=c, reason="test") for c in space[:2]]


def scripted(monkeypatch, store, grant_claims, slush_claims, pick):
    asked = []

    async def sourced_answer(question):
        asked.append(question)
        return "", grant_claims if "grants" in question else slush_claims

    async def fake(prompt, schema, **kw):
        claims = [line.split("] ", 1)[1] for line in prompt.splitlines() if line.startswith("[")]
        return schema.model_validate({"names": [{"name": n, "claims": c} for n, c in pick(claims)]})

    monkeypatch.setattr(store, "sourced_answer", sourced_answer)
    monkeypatch.setattr(fresh, "structured", fake)
    return asked


async def test_notes_keep_sourced_claims_about_the_competitors(store, monkeypatch):
    company, comps = await rivals(store)
    a, b = comps[0].company.name, comps[1].company.name
    won = Reason(text=f"{a} won NATO DIANA 2026 Phase I funding of €100k.", sources=[SRC])
    other = Reason(text="Acme Drones won an EIC grant.", sources=[SRC])
    bare = Reason(text=f"{b} won an EDF grant.", sources=[])
    there = Reason(text=f"{b} will exhibit at Slush 2026.", sources=[SRC])

    def pick(claims):
        out = []
        for n, text in enumerate(claims, start=1):
            for name in (a, b, "Acme Drones"):
                if name in text:
                    out.append((name, [n]))
        return out

    asked = scripted(monkeypatch, store, [won, other, bare], [there], pick)
    got = await REAL_NOTES(company, comps)
    assert [r.text for r in got] == [
        f"Non-dilutive: {won.text}",  # Acme is no competitor; the unsourced claim is never offered
        f"At Slush 2026: {there.text}",
    ]
    assert all(r.sources == [SRC] for r in got)
    assert a in asked[0] and b in asked[0]  # the question names the competitors
    assert await REAL_NOTES(company, comps) == got and len(asked) == 2  # stored


async def test_no_competitors_no_question(store, monkeypatch):
    company, _ = await rivals(store)
    asked = scripted(monkeypatch, store, [], [], lambda claims: [])
    assert await REAL_NOTES(company, []) == [] and asked == []


async def test_the_report_carries_the_notes(store, monkeypatch):
    company, comps = await rivals(store)
    line = Reason(text="Non-dilutive: X won DIANA.", sources=[SRC])

    async def fake_notes(company, competitors):
        return [line]

    monkeypatch.setattr(scoring, "report_notes", fake_notes)
    report = await rank_investors(company, comps, [], today=TODAY, notes=True)
    assert report.notes == [line]
    assert (await rank_investors(company, comps, [], today=TODAY)).notes == []
