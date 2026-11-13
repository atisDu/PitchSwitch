"""Sample API responses for the frontend mock (task A2): reports, checks, briefs, event streams.

These are SAMPLES. The facts are real Cala data from the fixtures, but which companies count as
direct competitors, the scores and the wording come from the simple rules below, not from B's
core (Gemini judging + scoring). B's API replaces them at checkpoint CP3.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

from contracts.schemas import (
    AgentEvent,
    Brief,
    Company,
    Competitor,
    Conflict,
    EntityRef,
    FounderReport,
    InvestorCheck,
    InvestorScore,
    Reason,
    Round,
    Source,
)
from data.mappers import merge_sources

if TYPE_CHECKING:
    from data.build_fixtures import Graph, Writer

N_DIRECT = 4  # direct competitors per company in a sample
N_BRIEFS = 6  # briefs written per founder report (top of pitch and skip)

# Demo companies that compete head-on (contracts/fixtures/README.md).
DEMO_SEGMENTS = {
    "counter-drone": ["sensofusion", "stendr", "nordic-air-defence"],
    "defence intelligence and autonomy": ["kelluu", "nestai"],
}

_STOP = set(
    "a an and are as at based by company companies developing for founded from headquartered "
    "in is it its of on or that the this to with which firm startup technology".split()
)


def _words(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in _STOP}


def similarity(a: Company, b: Company) -> float:
    """Word overlap of two descriptions, 0-1."""
    left, right = _words(a.description), _words(b.description)
    return round(len(left & right) / len(left | right), 3) if left and right else 0.0


class Samples:
    def __init__(self, graph: Graph, pool: list[Company]) -> None:
        self.graph = graph
        self.pool = pool
        today = date.fromisoformat(graph.recorded_on) if graph.recorded_on else date.today()
        self.year_ago = (today - timedelta(days=365)).isoformat()
        self.two_years_ago = (today - timedelta(days=730)).isoformat()
        self.case_ids = {
            key: case["id"] for key, case in graph.cases["company"].items() if case.get("id")
        }

    # --- competitors ---------------------------------------------------------------------------

    def competitors(self, company: Company) -> list[Competitor]:
        segment, rivals = None, set()
        for name, keys in DEMO_SEGMENTS.items():
            ids = {self.case_ids[k] for k in keys if k in self.case_ids}
            if company.id in ids:
                segment, rivals = name, ids - {company.id}
        scored = [(c, similarity(company, c)) for c in self.pool if c.id != company.id]
        scored.sort(key=lambda pair: (pair[0].id not in rivals, -pair[1], pair[0].name.lower()))
        result = []
        for other, score in scored[:N_DIRECT]:
            if other.id in rivals:
                reason = f"Same segment: {segment}."
            else:
                place = f" in {other.country}" if other.country else ""
                reason = f"Defence technology company{place} at a similar stage."
            result.append(Competitor(company=other, reason=reason, similarity=score))
        return result

    # --- one investor against one company ------------------------------------------------------

    def score(self, investor_id: str, company: Company, direct: list[Competitor]) -> InvestorScore:
        graph = self.graph
        links = graph.links.get(investor_id, {})
        space = {c.id for c in self.pool} - {company.id}
        names = {c.id: c.name for c in self.pool}
        all_rounds = graph.investor_rounds(investor_id)
        in_space = [r for r in all_rounds if r.company_id in space]

        def led(item: Round) -> bool | None:
            return next((i.is_lead for i in item.investors if i.investor.id == investor_id), None)

        leads = [r for r in in_space if led(r) is True]
        flagged = [r for r in in_space if led(r) is not None]
        backed = [links[c] for c in sorted(space & set(links), key=lambda c: names[c].lower())]
        if not flagged:
            lead_data = "unknown"
        elif len(flagged) == len(in_space) and len(in_space) >= len(backed):
            lead_data = "known"
        else:
            lead_data = "partial"

        reasons = []
        with_round = set()
        for item in in_space:
            with_round.add(item.company_id)
            verb = "Led" if led(item) is True else "Joined"
            detail = ", ".join(x for x in (item.date, item.amount_text) if x)
            text = f"{verb} {names[item.company_id]}'s {item.label or 'funding'} round"
            reasons.append(
                Reason(text=f"{text} ({detail})" if detail else text, sources=item.sources)
            )
        for link in backed:
            if link.company.id not in with_round:
                reasons.append(Reason(text=f"Backs {link.company.name}", sources=link.sources))

        led_dated = sorted(
            (r for r in all_rounds if led(r) is True and r.date), key=lambda r: r.date
        )
        last_lead = led_dated[-1] if led_dated else None
        if last_lead:
            reasons.append(
                Reason(
                    text=f"Last lead: {graph.name(last_lead.company_id)}, {last_lead.date}",
                    sources=last_lead.sources,
                )
            )

        conflicts = []
        for rival in direct:
            link = links.get(rival.company.id)
            ref = EntityRef(
                **rival.company.model_dump(include={"id", "name", "type", "description"})
            )
            if link:
                conflicts.append(Conflict(kind="PORTFOLIO", competitor=ref, sources=link.sources))
            partners = {p.person.id for p in graph.people.get(investor_id, [])}
            for seat in graph.people.get(rival.company.id, []):
                if seat.role == "BOARD" and seat.person.id in partners:
                    conflicts.append(
                        Conflict(
                            kind="BOARD",
                            competitor=ref,
                            via_person=seat.person,
                            sources=seat.sources,
                        )
                    )

        own_backers = {link.investor_id for link in graph.backers(company.id)}
        warm = []
        for other, count in graph.co_investors(investor_id):
            if other.id in own_backers:
                shared = sorted(set(links) & set(graph.links[other.id]))[:3]
                sources = merge_sources(*[links[c].sources for c in shared])[:4]
                noun = "company" if count == 1 else "companies"
                warm.append(
                    Reason(text=f"Co-invested with {other.name} in {count} {noun}", sources=sources)
                )

        dates = [r.date for r in all_rounds if r.date]
        latest = max(dates) if dates else ""
        recency = 30 if latest >= self.year_ago else 15 if latest >= self.two_years_ago else 0
        rounds_in_space = max(len(in_space), len(backed))
        points = 25 * len(leads) + 10 * rounds_in_space + recency + 10 * len(warm)
        return InvestorScore(
            investor=graph.refs[investor_id],
            score=float(min(100, points)),
            conflicts=conflicts,
            leads_in_space=len(leads),
            rounds_in_space=rounds_in_space,
            lead_data=lead_data,
            last_lead_date=last_lead.date if last_lead else None,
            deals_last_12m=sum(d >= self.year_ago for d in dates) if all_rounds else None,
            warm_paths=warm,
            reasons=reasons,
        )

    # --- API responses ---------------------------------------------------------------------------

    def founder_report(self, company: Company) -> FounderReport:
        direct = self.competitors(company)
        space = {c.id for c in self.pool} - {company.id}
        own_backers = {link.investor_id for link in self.graph.backers(company.id)}
        scores = [
            self.score(investor_id, company, direct)
            for investor_id in self.graph.investor_ids()
            if investor_id not in own_backers
            and investor_id != company.id
            and space & set(self.graph.links[investor_id])
        ]
        scores.sort(key=lambda s: (-s.score, s.investor.name.lower()))
        return FounderReport(
            company=company,
            competitors=direct,
            pitch=[s for s in scores if not s.conflicts],
            skip=[s for s in scores if s.conflicts],
        )

    def investor_check(self, investor_id: str, company: Company) -> InvestorCheck:
        direct = self.competitors(company)
        score = self.score(investor_id, company, direct)
        rounds = list(self.graph.rounds_of(company.id))
        for rival in direct:
            rounds.extend(self.graph.rounds_of(rival.company.id))
        return InvestorCheck(
            investor=self.graph.refs[investor_id],
            company=company,
            conflicts=score.conflicts,
            competitors=direct,
            rounds=rounds,
        )

    def brief(self, score: InvestorScore, company: Company) -> Brief:
        cites = _Citations()
        investor = score.investor
        lines = [f"# {investor.name} × {company.name}", ""]
        if score.conflicts:
            first = score.conflicts[0]
            how = (
                f"{first.via_person.name} sits on the board of"
                if first.kind == "BOARD" and first.via_person
                else f"{investor.name} backs"
            )
            lines.append(
                f"**Verdict: skip.** {how} {first.competitor.name}, a direct competitor"
                f"{cites.mark(first.sources)}."
            )
            for extra in score.conflicts[1:]:
                lines.append(f"- Also tied to {extra.competitor.name}{cites.mark(extra.sources)}.")
        else:
            lines.append(
                "**Verdict: worth a pitch.** No tie to your direct competitors in Cala's data."
            )
        lines += ["", "## Activity in your space"]
        if score.reasons:
            lines += [f"- {reason.text}{cites.mark(reason.sources)}." for reason in score.reasons]
        else:
            lines.append("- No recorded investments in your space.")
        if score.lead_data != "known":
            lines.append(
                "- Lead investors are not marked on every round, so the lead count may be low."
            )
        portfolio = self.graph.portfolio(investor.id)
        if portfolio:
            shown = portfolio[:5]
            names = ", ".join(link.company.name for link in shown)
            sources = merge_sources(*[link.sources for link in shown])
            lines += [
                "",
                "## Portfolio",
                f"- {len(portfolio)} companies in Cala, including {names}{cites.mark(sources, 3)}.",
            ]
        if score.warm_paths:
            lines += ["", "## Warm paths"]
            lines += [f"- {path.text}{cites.mark(path.sources)}." for path in score.warm_paths]
        return Brief(
            investor_id=investor.id,
            company_id=company.id,
            markdown="\n".join(lines) + "\n",
            citations=cites.sources,
        )


class _Citations:
    """Numbers sources in order of first use: the [n] markers of a brief or a chat answer."""

    def __init__(self) -> None:
        self.sources: list[Source] = []
        self._numbers: dict[tuple[str, str | None], int] = {}

    def mark(self, sources: list[Source], limit: int = 2) -> str:
        marks = []
        for source in sources[:limit]:
            key = (source.name, source.url)
            if key not in self._numbers:
                self.sources.append(source)
                self._numbers[key] = len(self.sources)
            marks.append(f"[{self._numbers[key]}]")
        return " " + "".join(marks) if marks else ""


def write_samples(
    graph: Graph,
    out: Writer,
    pool: list[Company],
    founder_keys: list[str],
    investor_pairs: list[tuple[str, str]],
) -> dict:
    """Write the sample responses; return what index.json should say about them."""
    samples = Samples(graph, pool)
    companies, investors = graph.cases["company"], graph.cases["investor"]
    briefs: dict[tuple[str, str], Brief] = {}
    info: dict = {
        "samples_note": (
            "founder_report_*, investor_check_*, brief_* and agent_events_* are samples: real "
            "Cala facts, placeholder competitor choice, scores and wording (see "
            "backend/data/sample_responses.py). B's API replaces them at CP3."
        ),
        "founder_mode": [],
        "investor_mode": [],
        "briefs": [],
    }

    def add_brief(score: InvestorScore, company: Company) -> Brief:
        key = (score.investor.id, company.id)
        if key not in briefs:
            briefs[key] = samples.brief(score, company)
            name = f"brief_{key[0]}_{key[1]}.json"
            out.write(name, briefs[key])
            info["briefs"].append({"investor_id": key[0], "company_id": key[1], "file": name})
        return briefs[key]

    reports: dict[str, FounderReport] = {}
    for key in founder_keys:
        company = graph.companies.get(companies.get(key, {}).get("id") or "")
        if company is None:
            continue
        report = samples.founder_report(company)
        reports[key] = report
        name = f"founder_report_{company.id}.json"
        out.write(name, report)
        info["founder_mode"].append({"key": key, "company_id": company.id, "file": name})
        half = N_BRIEFS // 2
        for score in [*report.pitch[: N_BRIEFS - min(half, len(report.skip))], *report.skip[:half]]:
            add_brief(score, company)

    for investor_key, company_key in investor_pairs:
        investor_id = investors.get(investor_key, {}).get("id")
        company = graph.companies.get(companies.get(company_key, {}).get("id") or "")
        if company is None or investor_id not in graph.refs:
            continue
        name = f"investor_check_{investor_id}_{company.id}.json"
        out.write(name, samples.investor_check(investor_id, company))
        info["investor_mode"].append(
            {
                "investor_key": investor_key,
                "investor_id": investor_id,
                "company_key": company_key,
                "company_id": company.id,
                "file": name,
            }
        )
        add_brief(samples.score(investor_id, company, samples.competitors(company)), company)

    # Event streams, for the first founder-mode company that has a report.
    for report in reports.values():
        company = report.company
        scores = [*report.skip[:1], *report.pitch[:2]]
        if not scores:
            continue
        unknown = "Nonexistent Capital"
        events = []
        for score in scores:
            pasted = score.investor.name
            events += [
                AgentEvent(
                    type="step", message=f"Looking up {pasted} in Cala", investor_name=pasted
                ),
                AgentEvent(
                    type="step",
                    message=f"Found {score.investor.name}. Checking conflicts and recent rounds",
                    investor_name=pasted,
                    investor=score.investor,
                ),
                AgentEvent(
                    type="brief",
                    brief=add_brief(score, company),
                    investor_name=pasted,
                    investor=score.investor,
                ),
            ]
        events += [
            AgentEvent(type="step", message=f"Looking up {unknown} in Cala", investor_name=unknown),
            AgentEvent(
                type="error",
                message=f'No investor named "{unknown}" found in Cala',
                investor_name=unknown,
            ),
            AgentEvent(type="done"),
        ]
        out.write("agent_events_slush_prep.json", events)
        info["slush_prep"] = {
            "company_id": company.id,
            "investor_names": [s.investor.name for s in scores] + [unknown],
            "file": "agent_events_slush_prep.json",
        }

        subject = scores[0]
        cites = _Citations()
        parts = [f"{reason.text}{cites.mark(reason.sources)}." for reason in subject.reasons[:4]]
        for conflict in subject.conflicts[:2]:
            parts.append(
                f"Conflict: {subject.investor.name} is tied to your competitor "
                f"{conflict.competitor.name}{cites.mark(conflict.sources)}."
            )
        words = " ".join(parts).split(" ")
        chunks = [" ".join(words[i : i + 5]) for i in range(0, len(words), 5)]
        chat = [
            AgentEvent(type="step", message=f"Reading {subject.investor.name}'s rounds in Cala"),
            AgentEvent(type="step", message=f"Comparing with {company.name}'s competitors"),
            *[
                AgentEvent(type="text", message=chunk + ("" if i == len(chunks) - 1 else " "))
                for i, chunk in enumerate(chunks)
            ],
            AgentEvent(type="done", citations=cites.sources),
        ]
        out.write("agent_events_chat.json", chat)
        info["chat"] = {
            "company_id": company.id,
            "investor_id": subject.investor.id,
            "message": f"What has {subject.investor.name} done in my space?",
            "file": "agent_events_chat.json",
        }
        break
    return info
