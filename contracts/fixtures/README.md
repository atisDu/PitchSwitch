# Fixtures — demo cases (task T3)

Picked by the team on 13 Nov. Task A1 records raw Cala responses for these into `raw/`; task A2
builds contract models from them into `models/` (file list: `contracts/api.md` → Fixtures).
`models/index.json` holds the Cala IDs. Always use IDs, never names, as keys.

## Founder mode — 3 companies

| Company | Why |
| --- | --- |
| **Kelluu** (Finland, ISR airships, Series A) | Best-covered case: Series A led by NATO Innovation Fund, with Keen Venture Partners, Gungnir Capital and Tesi. Shows "who leads in your space". |
| **Sensofusion** (Finland, counter-drone) | Counter-drone set: its rivals' backers land on the Skip list. |
| **Nordic Air Defence** (Sweden, counter-drone) | Counter-drone set, second viewpoint on the same rivals. |

## Investor mode — 2 pairs (fund + startup that pitched)

| Fund | Startup | Why |
| --- | --- | --- |
| **Tesi** | **NestAI** (Finland, defence AI) | Tesi backs both Kelluu and NestAI: a live portfolio overlap for the conflict moment. |
| **Maki.vc** | **Stendr** (Norway, counter-drone) | Maki.vc leads defence pre-seeds (Aavuus, Metaktik); Stendr competes with Sensofusion and Nordic Air Defence. |

## Counter-drone set (the conflict moment)

Sensofusion, Stendr, Nordic Air Defence. Any investor behind one of them is a conflict for the
other two.

## Investors to record (~10)

NATO Innovation Fund, Keen Venture Partners, Gungnir Capital, Tesi, Maki.vc, Inventure, plus the
investors that appear in the rounds of the five companies above.

## Known traps

- Cala often has two entries for one firm, a `Company` and an `Organization` (e.g. "Kelluu Oy" and
  "Kelluu", two "Maki.vc"s). The one with funding rounds and investors attached is the right one.
- Name search is fuzzy: "Nordic Air Defence" also returns a UK shell company and Thales Air Defence.
- There are several unrelated "Inventure"s and "Tesi"s; the investors are the Finnish ones.

## Coverage found while recording (A1, 13 Nov)

- **Nordic Air Defence has no company entity in Cala** (only text answers). It cannot be a
  founder-mode company, so **Stendr is the third founder-mode sample** (agreed with the team).
- **Sensofusion** has an entity but no rounds or investors attached. It works as the company a
  founder enters; it adds no backers to anyone's Skip list.
- **NestAI** has one investor edge and no rounds in the graph; `sourced_answer()` knows its round.
- Details and the other findings: `notes/A.md`.

## Rebuilding

```sh
python -m data.record_fixtures   # raw/: calls Cala (about 10 calls a minute), skips what exists
python -m data.build_fixtures    # models/: rebuilt from raw/, no network
```

Never edit `raw/` or `models/` by hand. A test fails if `models/` is not what
`build_fixtures` produces from `raw/`.
