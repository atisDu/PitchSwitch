"""Funding amount fit (B21): a founder's raise against the round sizes an investor joins, or an
investor's largest check against a company's round sizes. A flag on the card; never moves the
score. Cala's amounts are whole-round sizes, never one investor's share."""

from __future__ import annotations

from contracts.schemas import FundingFit, Round
from core.conflict import merge_sources

SLACK = 2  # a raise up to 2x off the usual round sizes still fits
MIN_SHARE = 0.1  # a check under 10% of the company's round is a small share
MAX_SOURCES = 6


def eur(x: float) -> str:
    for size, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= size:
            return f"€{x / size:.1f}".rstrip("0").rstrip(".") + unit
    return f"€{x:.0f}"


def _sized(rounds: list[Round]) -> list[Round]:
    """Rounds with an amount; grants are not equity rounds."""
    return [rd for rd in rounds if rd.amount_eur and "grant" not in (rd.label or "").lower()]


def _sources(rounds: list[Round]):
    return merge_sources(*(rd.sources for rd in rounds))[:MAX_SOURCES]


def raise_fit(target: float, history: list[Round], investor: str) -> FundingFit:
    """Founder mode: `target` against the middle half of the round sizes `investor` joined."""
    sized = sorted(_sized(history), key=lambda rd: rd.amount_eur)
    if not sized:
        return FundingFit(verdict="unknown", text=f"Cala has no round sizes for {investor}")
    cut = len(sized) // 4 if len(sized) >= 4 else 0  # drop outliers at both ends
    middle = sized[cut : len(sized) - cut]
    lo, hi = middle[0].amount_eur, middle[-1].amount_eur
    span = eur(lo) if lo == hi else f"{eur(lo)}-{eur(hi)}"
    n = f"{len(sized)} round{'s' if len(sized) != 1 else ''} with amounts"
    if target < lo / SLACK:
        verdict, end = "too_small", f"your {eur(target)} raise is smaller"
    elif target > hi * SLACK:
        verdict, end = "too_large", f"your {eur(target)} raise is bigger"
    else:
        verdict, end = "fits", f"your {eur(target)} raise fits"
    return FundingFit(
        verdict=verdict, text=f"Joins rounds of {span} ({n}); {end}", sources=_sources(middle)
    )


def check_fit(max_check: float, rounds: list[Round], company: str) -> FundingFit:
    """Investor mode: `max_check` against the company's latest round with an amount."""
    sized = _sized(rounds)
    if not sized:
        return FundingFit(verdict="unknown", text=f"Cala has no round sizes for {company}")
    last = max(sized, key=lambda rd: rd.date or "")
    size = last.amount_eur
    what = f"{company}'s latest round{f' ({last.label})' if last.label else ''} was {eur(size)}"
    sep = ";"
    if max_check > size:
        verdict, sep, end = "too_small", ",", f"less than your {eur(max_check)} check"
    elif max_check < size * MIN_SHARE:
        verdict, end = "too_large", f"your {eur(max_check)} would be under 10% of it"
    else:
        verdict, end = "fits", f"your {eur(max_check)} check fits"
    return FundingFit(verdict=verdict, text=f"{what}{sep} {end}", sources=_sources([last]))
