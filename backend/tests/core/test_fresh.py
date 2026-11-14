"""B23 fresh funds and lead partners on the fake store, with scripted Cala search and Gemini."""

from datetime import date

import pytest

import core.fresh as fresh
import core.scoring as scoring
from contracts.schemas import Competitor, EntityRef, PersonLink, Reason, Source
from core.scoring import rank_investors
from data import get_store

KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
TODAY = date(2026, 11, 13)
REAL_FUNDS, REAL_PARTNER = fresh.fresh_funds, fresh.lead_partner
SRC = Source(name="Press", url="https://example.com/a", rank="PRESS")


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


def extractor(answer):
    """Fake `structured` for the name extraction: answer(claim texts) -> [(name, [numbers])]."""
    calls = []

    async def fake(prompt, schema, **kw):
        claims = [line.split("] ", 1)[1] for line in prompt.splitlines() if line.startswith("[")]
        calls.append(claims)
        named = [{"name": n, "claims": c} for n, c in answer(claims)]
        return schema.model_validate({"names": named})

    return fake, calls


def searched(monkeypatch, store, claims):
    asked = []

    async def sourced_answer(question):
        asked.append(question)
        return "", claims

    monkeypatch.setattr(store, "sourced_answer", sourced_answer)
    return asked


async def test_names_must_appear_in_a_claim_they_cite(monkeypatch):
    claims = [Reason(text="Keen Venture Partners closed a €150M fund.", sources=[SRC])]
    fake, _ = extractor(
        lambda c: [
            ("Keen Venture Partners", [1]),
            ("Lakestar", [1]),
            ("Keen Venture Partners", [1]),
            ("Ghost", [9]),
        ]
    )
    monkeypatch.setattr(fresh, "structured", fake)
    got = await fresh._names(claims, "ask")
    assert [n for n, _ in got] == ["Keen Venture Partners"]  # invented, repeated, bad index: out


async def test_fresh_funds_resolve_and_are_stored_once(store, monkeypatch):
    company = await store.company(KELLUU)
    claims = [
        Reason(text="Keen Venture Partners completed a first close above €150M.", sources=[SRC]),
        Reason(text="Acme Robotics raised a fund for drones.", sources=[SRC]),
        Reason(text="Unsourced Capital closed a fund.", sources=[]),
    ]
    asked = searched(monkeypatch, store, claims)
    fake, calls = extractor(lambda c: [("Keen Venture Partners", [1]), ("Acme Robotics", [2])])
    monkeypatch.setattr(fresh, "structured", fake)
    keen = EntityRef(
        id="keen",
        name="Keen Venture Partners B.V.",
        type="Organization",
        description="Venture capital firm",
    )
    acme = EntityRef(id="acme", name="Acme Robotics", type="Company", description="Robots")

    async def resolve(name, kind):
        return {"Keen Venture Partners": [keen], "Acme Robotics": [acme]}.get(name, [])

    monkeypatch.setattr(store, "resolve", resolve)

    got = await REAL_FUNDS(fresh.sector_of(company), TODAY)
    assert [ref.id for ref, _ in got] == ["keen"]  # Acme is no investor
    why = got[0][1]
    assert why.text.startswith("Fresh fund: Keen Venture Partners completed") and why.sources == [
        SRC
    ]
    assert calls[0] == [claims[0].text, claims[1].text]  # unsourced claims are never offered
    assert await REAL_FUNDS(fresh.sector_of(company), TODAY) == got and len(asked) == 1  # stored


async def test_lead_partner_is_stored_and_needs_a_full_name(store, monkeypatch):
    nif = EntityRef(id="nif", name="NATO Innovation Fund", type="Organization")
    claims = [
        Reason(
            text="Patrick Schneider-Sikorsky is a Partner at the NATO Innovation Fund.",
            sources=[SRC],
        )
    ]
    asked = searched(monkeypatch, store, claims)
    fake, _ = extractor(lambda c: [("Patrick Schneider-Sikorsky", [1])])
    monkeypatch.setattr(fresh, "structured", fake)

    assert await REAL_PARTNER(nif, "defence", look_up=False) is None  # nothing stored yet
    partner = await REAL_PARTNER(nif, "defence")
    assert partner["name"] == "Patrick Schneider-Sikorsky"
    assert partner["reason"]["text"].startswith("Partner for your space: Patrick")
    assert await REAL_PARTNER(nif, "defence", look_up=False) == partner and len(asked) == 1

    keen = EntityRef(id="keen", name="Keen", type="Organization")
    first_only = [Reason(text="Giuseppe leads defence at Keen.", sources=[SRC])]
    searched(monkeypatch, store, first_only)
    monkeypatch.setattr(fresh, "structured", extractor(lambda c: [("Giuseppe", [1])])[0])
    assert await REAL_PARTNER(keen, "defence") is None


async def test_board_conflict_by_the_partners_name(store, monkeypatch):
    rival = Competitor(company=await store.company(KELLUU), reason="test")
    person = EntityRef(id="p1", name="Patrick Schneider‑Sikorsky", type="Person")

    async def people(company_id):
        return [
            PersonLink(person=person, company_id=company_id, role="BOARD", sources=[SRC]),
            PersonLink(person=person, company_id=company_id, role="EMPLOYEE", sources=[]),
        ]

    monkeypatch.setattr(store, "people", people)
    partner = {
        "name": "Patrick Schneider-Sikorsky",
        "reason": Reason(text="Partner for your space: ...", sources=[SRC]).model_dump(),
    }
    got = await fresh.board_conflicts(partner, [rival])
    assert [(c.kind, c.competitor.id, c.via_person.id) for c in got] == [("BOARD", KELLUU, "p1")]
    other = {**partner, "name": "Someone Else"}
    assert await fresh.board_conflicts(other, [rival]) == []


async def test_report_adds_fresh_funds_and_skips_a_partner_on_a_rivals_board(store, monkeypatch):
    company = await store.company(KELLUU)
    space = await store.candidate_competitors(company)
    rival = Competitor(company=space[0], reason="test")
    base = await rank_investors(company, [rival], space[1:], today=TODAY)
    top = base.pitch[0]
    newcomer = EntityRef(
        id="fresh-1", name="Fresh Capital", type="Organization", description="Venture capital firm"
    )
    fund = Reason(text="Fresh fund: Fresh Capital closed €100M for defence.", sources=[SRC])

    async def funds(sector, today=None):
        return [(newcomer, fund)]

    async def partner(investor, sector, look_up=True):
        if investor.id != top.investor.id:
            return None
        return {
            "name": "Jane Partner",
            "reason": Reason(
                text="Partner for your space: Jane Partner.", sources=[SRC]
            ).model_dump(),
        }

    jane = EntityRef(id="jane", name="Jane Partner", type="Person")

    async def people(company_id):  # Jane sits on the rival's board; nobody else has people
        if company_id != rival.company.id:
            return []
        return [PersonLink(person=jane, company_id=company_id, role="BOARD", sources=[SRC])]

    monkeypatch.setattr(scoring, "fresh_funds", funds)
    monkeypatch.setattr(scoring, "lead_partner", partner)
    monkeypatch.setattr(store, "people", people)

    after = await rank_investors(company, [rival], space[1:], today=TODAY, this_week=True)

    new = next(s for s in after.pitch if s.investor.id == "fresh-1")
    assert any(r.text.startswith("Fresh fund:") for r in new.reasons)
    assert "activity 10/10 (fresh fund for your sector" in new.reasons[0].text
    skipped = next(s for s in after.skip if s.investor.id == top.investor.id)
    board = [c for c in skipped.conflicts if c.kind == "BOARD"]
    assert board and board[0].via_person.id == "jane" and board[0].competitor.id == rival.company.id
    assert any("its partner Jane Partner sits on the board of" in r.text for r in skipped.reasons)
    assert top.investor.id not in {s.investor.id for s in after.pitch}


async def test_sector_from_the_peers_when_the_startup_has_no_tag(store):
    company = await store.company(KELLUU)
    bare = company.model_copy(update={"industries": []})
    peer = company.model_copy(update={"id": "p", "industries": ["AEROSPACE_AND_DEFENSE"]})
    other = company.model_copy(update={"id": "q", "industries": ["SOFTWARE_AND_SERVICES"]})
    assert fresh.sector_of(bare, [peer, other, peer]) == "aerospace and defense"
    assert fresh.sector_of(bare) == "technology"
