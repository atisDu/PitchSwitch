"""investor_brief on the fake store with a scripted Gemini draft."""

import re

import pytest

import core.briefs as briefs
from contracts.schemas import Competitor, Reason, Source
from data import get_store

STENDR = "3afdc63c-b992-4b25-b69d-807ab346352d"
KELLUU = "78d7490a-dd04-5119-a7f1-e940b861219b"
NIF = "2ca07622-990d-40bf-a4fe-36434d43d6db"
MAKI = "415bc278-6ed1-4973-a684-07a8b8c5d855"
A, B, C = (Source(name=n, url=f"https://{n}") for n in "abc")


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("USE_FAKE_STORE", "true")
    get_store.cache_clear()
    yield get_store()
    get_store.cache_clear()


def draft(*sections):
    return briefs._Draft.model_validate(
        {"sections": [{"heading": h, "sentences": [{"text": t, "facts": f} for t, f in ss]}
                      for h, ss in sections]}
    )


def test_render_cites_drops_and_numbers():
    facts = [
        Reason(text="Led Aavuus's Pre-Seed of €1.2M on 2026-06-09", sources=[A, B]),
        Reason(text="Backs Kelluu", sources=[B]),
        Reason(text="Took part in Metaktik's Seed", sources=[C]),
    ]
    md, cites = briefs.render(draft(
        ("Verdict", [
            ("They led a €1.2M pre-seed in 2026.", [1]),  # numbers in fact 1 -> kept
            ("They wrote a €5M cheque.", [1]),  # 5 is in no fact -> dropped
            ("No source for this.", []),  # cites nothing -> dropped
            ("Invented fact.", [9]),  # no fact 9 -> dropped
        ]),
        ("Conflicts", [("They back Kelluu.", [2, 2])]),
        ("Empty", [("Dropped too.", [])]),  # no sentence left -> no heading
    ), facts)

    assert cites == [A, B]  # C never cited, B reused
    assert md == (
        "## Verdict\n\nThey led a €1.2M pre-seed in 2026. [1][2]\n\n"
        "## Conflicts\n\nThey back Kelluu. [2]"
    )


async def test_brief_end_to_end_conflict_first(store, monkeypatch):
    stendr = await store.company(STENDR)
    rivals = [Competitor(company=await store.company(KELLUU), reason="test")]
    seen = {}

    async def fake(prompt, schema, **kw):
        seen["prompt"], seen["tier"] = prompt, kw.get("tier")
        lines = [ln for ln in prompt.splitlines() if re.match(r"\d+\. ", ln)]
        conflict = next(int(ln.split(".")[0]) for ln in lines if "Conflict:" in ln)
        return draft(
            ("Verdict", [("Skip: they back a direct competitor.", [conflict])]),
            ("Recent activity", [(lines[-1].split(". ", 1)[1], [len(lines)])]),
        )

    monkeypatch.setattr(briefs, "structured", fake)
    brief = await briefs.investor_brief(NIF, STENDR, rivals, [])

    assert brief.investor_id == NIF and brief.company_id == stendr.id
    assert seen["tier"] == "smart" and "Kelluu" in seen["prompt"]
    assert brief.markdown.startswith("## Verdict\n\nSkip: they back a direct competitor. [")
    markers = {int(n) for n in re.findall(r"\[(\d+)\]", brief.markdown)}
    assert markers == set(range(1, len(brief.citations) + 1))  # every citation used, none dangling
    for sentence in re.split(r"(?<=\])\s+|\n\n", brief.markdown):
        assert sentence.startswith("## ") or re.search(r"\[\d+\]$", sentence)


async def test_every_fact_offered_has_sources(store):
    stendr = await store.company(STENDR)
    rivals = [Competitor(company=await store.company(KELLUU), reason="test")]
    space = await store.candidate_competitors(stendr)
    name, facts = await briefs.collect_facts(MAKI, stendr, rivals, space)
    assert name == "Maki.vc" and len(facts) > 3
    assert all(f.sources for f in facts)
    assert any(f.text.startswith("Led ") for f in facts)  # Maki.vc's pre-seed leads
    assert any(f.text.startswith("Cala: ") for f in facts)  # the sourced answer
