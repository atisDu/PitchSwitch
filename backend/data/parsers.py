"""Text -> numbers and dates (task A5).

Cala's structured rounds carry numeric amounts, but `knowledge_query` rows and answers give text
such as "~€15M", "over $100M" or "Oct 2025". These parsers never raise: text they can't read
becomes None.
"""

from __future__ import annotations

import re

# Fixed rates to EUR, good enough for ranking (not for accounting).
FX_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
    "SEK": 0.088,
    "NOK": 0.086,
    "DKK": 0.134,
    "CHF": 1.05,
}

_SIGNS = {"€": "EUR", "$": "USD", "£": "GBP"}
_CODES = "|".join(FX_TO_EUR)
_SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "mm": 1e6,
    "mio": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
}
_NUMBER = r"(?P<number>\d[\d.,\s]*\d|\d)"
_SCALE = r"(?P<scale>billion|million|thousand|mio|bn|mn|mm|[kmb])?"
# "€15M", "$ 4.2 million", "EUR 15m", "USD4.2bn"
_BEFORE = re.compile(
    rf"(?P<currency>[€$£]|\b(?:{_CODES})\b)\s*{_NUMBER}\s*{_SCALE}(?![a-z])", re.IGNORECASE
)
# "15 MEUR", "1.5M€", "20 million SEK", "15 M€"
_AFTER = re.compile(rf"{_NUMBER}\s*{_SCALE}\s*(?P<currency>[€$£]|(?:{_CODES})\b)", re.IGNORECASE)

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))
_YEAR = r"(?P<year>(?:19|20)\d{2})"
_ISO = re.compile(r"\b(?P<year>(?:19|20)\d{2})-(?P<month>\d{2})(?:-(?P<day>\d{2}))?\b")
_DAY_MONTH_YEAR = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\.?\s+(?P<month>{_MONTH})\.?,?\s+{_YEAR}\b",
    re.IGNORECASE,
)
_MONTH_DAY_YEAR = re.compile(
    rf"\b(?P<month>{_MONTH})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR}\b", re.IGNORECASE
)
_MONTH_YEAR = re.compile(rf"\b(?P<month>{_MONTH})\.?,?\s+{_YEAR}\b", re.IGNORECASE)
_YEAR_ONLY = re.compile(rf"\b{_YEAR}\b")


def _number(text: str) -> float | None:
    """'1,500,000' -> 1500000.0, '1,5' -> 1.5, '4.2' -> 4.2, '15 000' -> 15000.0."""
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")  # 1,500,000.50
    elif "," in text:
        parts = text.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            text = ".".join(parts)  # 1,5 = one and a half (European decimal comma)
        else:
            text = "".join(parts)  # 1,500 or 1,500,000
    elif text.count(".") > 1:
        text = text.replace(".", "")  # 1.500.000
    try:
        return float(text)
    except ValueError:
        return None


def parse_amount(text: str | None) -> tuple[float, str] | None:
    """The first money amount in the text as (value, currency code), or None.

    "~€15M" -> (15000000.0, "EUR"); "over $100M" -> (100000000.0, "USD");
    "€100 million (~$115-116M)" -> (100000000.0, "EUR"); "undisclosed" -> None.
    """
    if not text or not isinstance(text, str):
        return None
    matches = [m for m in (_BEFORE.search(text), _AFTER.search(text)) if m]
    if not matches:
        return None
    match = min(matches, key=lambda m: m.start())
    value = _number(match["number"])
    if value is None:
        return None
    currency = match["currency"]
    currency = _SIGNS.get(currency, currency.upper())
    scale = _SCALES.get((match["scale"] or "").lower(), 1.0)
    return value * scale, currency


def to_eur(value, units: str | None) -> float | None:
    """A numeric amount in `units` as EUR, or None if either is unusable."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    rate = FX_TO_EUR.get((units or "").upper())
    return round(float(value) * rate, 2) if rate else None


def amount_eur(text: str | None) -> float | None:
    """Amount text -> EUR. "~€15M" -> 15000000.0; "$12M" -> 11040000.0; unreadable -> None."""
    parsed = parse_amount(text)
    return to_eur(*parsed) if parsed else None


def parse_date(text: str | None) -> str | None:
    """A date in the text as an ISO prefix: "2026-04-14", "2025-10" or "2026". Else None.

    "Oct 2025" -> "2025-10"; "14 April 2026" -> "2026-04-14"; "Q2 2025" -> "2025".
    """
    if not text or not isinstance(text, str):
        return None
    match = _ISO.search(text)
    if match and 1 <= int(match["month"]) <= 12:
        day = match["day"]
        if day and 1 <= int(day) <= 31:
            return f"{match['year']}-{match['month']}-{day}"
        return f"{match['year']}-{match['month']}"
    for pattern in (_DAY_MONTH_YEAR, _MONTH_DAY_YEAR):
        match = pattern.search(text)
        if match and 1 <= int(match["day"]) <= 31:
            month = _MONTHS[match["month"].lower()]
            return f"{match['year']}-{month:02d}-{int(match['day']):02d}"
    match = _MONTH_YEAR.search(text)
    if match:
        return f"{match['year']}-{_MONTHS[match['month'].lower()]:02d}"
    match = _YEAR_ONLY.search(text)
    return match["year"] if match else None
