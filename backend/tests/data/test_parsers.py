"""Amount and date text as Cala writes it -> EUR and ISO dates."""

import pytest

from data.parsers import amount_eur, parse_amount, parse_date, to_eur

AMOUNTS = [
    ("~€15M", (15_000_000.0, "EUR")),
    ("over $100M", (100_000_000.0, "USD")),
    ("$12M", (12_000_000.0, "USD")),
    ("€1M", (1_000_000.0, "EUR")),
    ("$4.2 million", (4_200_000.0, "USD")),
    ("~$9.09M", (9_090_000.0, "USD")),
    ("~$107M+", (107_000_000.0, "USD")),
    ("£2.3bn", (2_300_000_000.0, "GBP")),
    ("€500K", (500_000.0, "EUR")),
    ("EUR 15m", (15_000_000.0, "EUR")),
    ("15 MEUR", (15_000_000.0, "EUR")),
    ("1,5 M€", (1_500_000.0, "EUR")),
    ("20 million SEK", (20_000_000.0, "SEK")),
    ("€1,500,000", (1_500_000.0, "EUR")),
    ("€15 000", (15_000.0, "EUR")),
    ("€100 million (~$115–116M)", (100_000_000.0, "EUR")),
    ("~€15M (Series A, Apr 2026; NATO Innovation Fund's first", (15_000_000.0, "EUR")),
    ("Raised a €3.5M seed round backed by Maki.vc", (3_500_000.0, "EUR")),
    ("€15 backed", (15.0, "EUR")),
    ("undisclosed", None),
    ("Series A", None),
    ("Raised Seed round (Jun 2026), investor: Maki.vc", None),
    ("", None),
    (None, None),
    (15_000_000, None),
]


@pytest.mark.parametrize(("text", "expected"), AMOUNTS)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_amount_eur_converts_with_the_fixed_table():
    assert amount_eur("~€15M") == 15_000_000.0
    assert amount_eur("$12M") == 11_040_000.0
    assert amount_eur("over $100M") == 92_000_000.0
    assert amount_eur("£1M") == 1_170_000.0
    assert amount_eur("undisclosed") is None
    assert amount_eur(None) is None


def test_to_eur():
    assert to_eur(100.0, "EUR") == 100.0
    assert to_eur(100, "usd") == 92.0
    assert to_eur(100.0, "XXX") is None
    assert to_eur(100.0, None) is None
    assert to_eur("100", "EUR") is None
    assert to_eur(True, "EUR") is None


DATES = [
    ("Oct 2025", "2025-10"),
    ("October 2025", "2025-10"),
    ("Sept. 2024", "2024-09"),
    ("2026", "2026"),
    ("2026-04-14", "2026-04-14"),
    ("2025-10", "2025-10"),
    ("14 April 2026", "2026-04-14"),
    ("April 14, 2026", "2026-04-14"),
    ("November 20, 2025", "2025-11-20"),
    ("3rd Mar 2026", "2026-03-03"),
    ("Series A (Oct 2025)", "2025-10"),
    ("Raised Seed round (Jun 2026), investor: Maki.vc", "2026-06"),
    ("Q2 2025", "2025"),
    ("founded 2018", "2018"),
    ("2026-13-40", "2026"),
    ("May 2026", "2026-05"),
    ("no date here", None),
    ("12345", None),
    ("", None),
    (None, None),
    (2026, None),
]


@pytest.mark.parametrize(("text", "expected"), DATES)
def test_parse_date(text, expected):
    assert parse_date(text) == expected
