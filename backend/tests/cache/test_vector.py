"""Vector search over stored companies, with a fake embedder (no Gemini, no Atlas)."""

import pytest

from cache.graph import MemoryGraph
from cache.vector import COLLECTION, VectorStore, company_text, cosine
from contracts.schemas import Company

TOPICS = ["drone", "airship", "satellite", "dental"]


class FakeEmbedder:
    """One dimension per topic word: texts about the same thing point the same way."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(text.lower().count(topic)) + 0.01 for topic in TOPICS] for text in texts]


def company(company_id, name, description, industries=()):
    return Company(
        id=company_id, name=name, type="Company", description=description,
        industries=list(industries),
    )  # fmt: skip


SENSOFUSION = company("s", "Sensofusion", "Counter-drone systems: drone detection and jamming")
STENDR = company("t", "Stendr", "AI sensors for drone defence")
KELLUU = company("k", "Kelluu", "Hydrogen airship for surveillance")
REORBIT = company("r", "ReOrbit", "Satellite platforms")
DENTAL = company("d", "Toothly", "Dental booking software")


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def vectors(embedder):
    return VectorStore(graph=MemoryGraph(), embedder=embedder)


def test_company_text_and_cosine():
    with_industry = company("x", "Acme Oy.", "Builds radars.", ["AEROSPACE_AND_DEFENSE"])
    assert company_text(with_industry) == "Acme Oy. Builds radars. AEROSPACE_AND_DEFENSE"
    assert company_text(company("x", "Acme", None)) == "Acme"
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


async def test_each_company_is_embedded_once(vectors, embedder):
    assert await vectors.upsert([SENSOFUSION, STENDR, SENSOFUSION]) == 2
    assert len(embedder.calls) == 1 and len(embedder.calls[0]) == 2  # one batched call

    assert await vectors.upsert([SENSOFUSION, STENDR]) == 0  # stored: no Gemini call
    assert len(embedder.calls) == 1

    assert await vectors.upsert([STENDR, KELLUU]) == 1  # only the new one
    assert embedder.calls[-1] == [company_text(KELLUU)]

    renamed = STENDR.model_copy(update={"description": "Now builds airship sensors"})
    assert await vectors.upsert([renamed]) == 1  # the text changed: embedded again
    stored = await vectors.graph.get(COLLECTION, "t")
    assert stored["company"]["description"] == "Now builds airship sensors"
    assert "sources" not in stored["company"] and len(stored["embedding"]) == len(TOPICS)


async def test_neighbours_are_the_closest_companies_without_itself(vectors, embedder):
    await vectors.upsert([SENSOFUSION, STENDR, KELLUU, REORBIT, DENTAL])
    calls = len(embedder.calls)
    found = await vectors.neighbours(SENSOFUSION, k=3)
    assert len(embedder.calls) == calls  # Sensofusion's vector was stored: nothing embedded
    assert [c.name for c, _ in found][0] == "Stendr"
    assert "Sensofusion" not in [c.name for c, _ in found] and len(found) == 3
    scores = [score for _, score in found]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 1 for s in scores)
    assert scores[0] > 0.95 and scores[-1] < 0.9


async def test_neighbours_of_an_unstored_company_embed_just_that_one(vectors, embedder):
    await vectors.upsert([STENDR, DENTAL])
    newcomer = company("n", "DroneShield", "Drone detection radar")
    found = await vectors.neighbours(newcomer, k=1)
    assert embedder.calls[-1] == [company_text(newcomer)]
    assert [c.name for c, _ in found] == ["Stendr"]
    assert await VectorStore(graph=MemoryGraph(), embedder=embedder).neighbours(newcomer) == []
