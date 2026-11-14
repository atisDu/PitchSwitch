"""B21 funding fit: pure functions over rounds."""

from contracts.schemas import Round, Source
from core.funding import check_fit, eur, raise_fit

SRC = [Source(name="press", url="https://example.com")]


def rd(amount, label="Seed", when="2025-01-01", i="r"):
    return Round(id=f"{i}{amount}", company_id="c", label=label, date=when, amount_eur=amount,
                 sources=SRC)


def test_eur():
    assert [eur(x) for x in (301_500, 1_500_000, 15e6, 2.25e9, 900)] == [
        "€301.5K", "€1.5M", "€15M", "€2.2B", "€900"]


def test_raise_fit_uses_the_middle_half_and_2x_slack():
    history = [rd(x) for x in (0.2e6, 1e6, 2e6, 3e6, 5e6, 100e6)] + [rd(None)]
    fit = raise_fit(3e6, history, "Fund")
    assert fit.verdict == "fits" and fit.text.startswith("Joins rounds of €1M-€5M (6 rounds")
    assert fit.sources == SRC
    assert raise_fit(0.4e6, history, "Fund").verdict == "too_small"
    assert raise_fit(11e6, history, "Fund").verdict == "too_large"
    assert raise_fit(1e6, [rd(None), rd(5e5, label="Grant")], "Fund").verdict == "unknown"


def test_check_fit_against_the_latest_round():
    rounds = [rd(15e6, "Series A", "2025-06-01"), rd(1e6, "Seed", "2023-01-01"),
              rd(3e5, "Grant", "2026-01-01")]
    assert check_fit(3e6, rounds, "Kelluu").text == (
        "Kelluu's latest round (Series A) was €15M; your €3M check fits")
    assert check_fit(20e6, rounds, "Kelluu").text == (
        "Kelluu's latest round (Series A) was €15M, less than your €20M check")
    assert check_fit(1e6, rounds, "Kelluu").verdict == "too_large"
    assert check_fit(1e6, [], "Kelluu").verdict == "unknown"
