"""Agent tools (B12): the core functions as "IDs in, contract models out" tools.

The same functions serve the Gemini agent (agent/gemini_agent.py) and the MCP server
(mcp_server/server.py). For Gemini, `declaration()` builds the tool schema from a function's
signature and docstring, and `facts()` turns a result into sourced facts: the only material the
agent may build an answer from.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from collections.abc import Callable
from typing import Any, Literal

from google.genai import types
from pydantic import BaseModel, TypeAdapter

from contracts.schemas import (
    Brief,
    Company,
    Competitor,
    Conflict,
    EntityRef,
    FounderReport,
    PortfolioLink,
    Reason,
    Round,
)
from core import briefs, conflict, scoring
from core.competitors import shared_graph, stored_judgement
from core.xray import hidden_rivals
from data import NotFound, get_store

MAX_PROFILE_ROUNDS = 10  # most recent rounds in an investor profile
MAX_PORTFOLIO_FACTS = 40  # ponytail: a big fund's portfolio (Tesi: hundreds) is cut for the agent


class InvestorProfile(BaseModel):
    """Not a contract model: §5.4 names the tool, not its shape."""

    investor: Company
    rounds: list[Round]  # most recent first
    portfolio: list[PortfolioLink]
    companies: dict[str, str]  # id -> name for every Round.company_id above


_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def check_ids(*ids: str | None) -> None:
    """NotFound for anything that is not a Cala ID (a name, a typo, a broken link). Cala answers
    those with a format error, which would reach the caller as "data source unavailable"."""
    for i in ids:
        if i is not None and not _UUID.fullmatch(i):
            raise NotFound(
                f"No company or investor with that ID ({i!r}). IDs look like "
                f"202e9283-6455-486f-8868-03c7e0d0cf29; resolve_company finds one by name."
            )


# --- the tools ----------------------------------------------------------------------------------


async def resolve_company(
    name: str, kind: Literal["company", "investor"] = "company"
) -> list[EntityRef]:
    """Find a company (kind "company") or an investor (kind "investor") in Cala by name.
    Returns the matching entities with their IDs; every other tool takes these IDs."""
    return await get_store().resolve(name, kind)


async def find_competitors(company_id: str) -> list[Competitor]:
    """The direct competitors of a company, each with a one-line reason."""
    return (await stored_judgement(await get_store().company(company_id))).direct


async def get_rounds(company_id: str) -> list[Round]:
    """A company's funding rounds: label, date, amount, the investors and who led."""
    return await get_store().rounds(company_id)


async def investor_profile(investor_id: str) -> InvestorProfile:
    """An investor: what it is, its most recent funding rounds and its portfolio companies."""
    store = get_store()
    investor, rounds, portfolio = await asyncio.gather(
        store.company(investor_id), store.investor_rounds(investor_id), store.portfolio(investor_id)
    )
    recent = sorted(rounds, key=lambda r: r.date or "", reverse=True)[:MAX_PROFILE_ROUNDS]
    known = {link.company.id: link.company.name for link in portfolio}
    names = await briefs.company_names([rd.company_id for rd in recent], known)
    return InvestorProfile(
        investor=investor,
        rounds=recent,
        portfolio=portfolio,
        companies={rd.company_id: names[rd.company_id] for rd in recent if rd.company_id in names},
    )


async def check_conflict(investor_id: str, company_id: str) -> list[Conflict]:
    """Does this investor have a conflict with this company: has it backed one of the company's
    direct competitors, or does one of its people sit on a competitor's board? An empty list
    means no conflict was found."""
    store = get_store()
    # Looking the investor up too: a made-up ID must fail, not read as "no conflict".
    company, _ = await asyncio.gather(store.company(company_id), store.company(investor_id))
    judged = await stored_judgement(company)
    hidden = await hidden_rivals(company, investor_id, judged.direct, judged.space)
    return await conflict.check_conflict(investor_id, judged.direct, hidden=hidden)


async def rank_investors(company_id: str, limit: int = 10) -> FounderReport:
    """Who a company should pitch and who it should skip. `pitch` holds the `limit` best-fitting
    investors, best first; `skip` holds every investor with a conflict (it backs a direct
    competitor)."""
    company = await get_store().company(company_id)
    judged = await stored_judgement(company)
    space = [*(c.company for c in judged.direct), *judged.space]
    report = await scoring.rank_investors(company, judged.direct, space, xray=True)
    return report.model_copy(update={"pitch": report.pitch[: max(limit, 0)]})


async def investor_brief(investor_id: str, company_id: str) -> Brief:
    """A one-page, fully cited brief for the company's founder about one investor: pitch or
    skip, fit, recent activity, conflicts."""
    company = await get_store().company(company_id)
    judged = await stored_judgement(company)
    return await briefs.investor_brief(
        investor_id, company.id, judged.direct, judged.space, graph=shared_graph()
    )


async def sourced_answer(question: str) -> list[Reason]:
    """Ask Cala's knowledge search a free-form question about companies, investors or funding
    (e.g. "Who led Kelluu's Series A?"). Returns sourced claims. Use it for what the other tools
    don't cover."""
    return (await get_store().sourced_answer(question))[1]


# §5.4, in order. The agent adds sourced_answer; the MCP server exposes exactly these.
MCP_TOOLS: list[Callable] = [
    resolve_company,
    find_competitors,
    get_rounds,
    investor_profile,
    check_conflict,
    rank_investors,
    investor_brief,
]


# --- for Gemini ---------------------------------------------------------------------------------


def declaration(fn: Callable) -> types.FunctionDeclaration:
    """Gemini's schema for a tool: name, docstring and the JSON schema of its arguments."""
    return types.FunctionDeclaration(
        name=fn.__name__,
        description=inspect.getdoc(fn),
        parameters_json_schema=TypeAdapter(fn).json_schema(),
    )


def names_in(result: Any) -> dict[str, str]:
    """id -> name of every entity anywhere inside a tool result."""
    found: dict[str, str] = {}
    if isinstance(result, EntityRef):
        found[result.id] = result.name
    if isinstance(result, InvestorProfile):
        found |= result.companies
    if isinstance(result, BaseModel):
        result = list(vars(result).values())
    if isinstance(result, list | tuple):
        for item in result:
            found |= names_in(item)
    return found


def _round(rd: Round, names: dict[str, str]) -> Reason:
    who = names.get(rd.company_id, "a company")
    investors = ", ".join(
        ri.investor.name + (" (lead)" if ri.is_lead else "") for ri in rd.investors
    )
    if not rd.label and not rd.date:  # A7: backers known, round details not
        return Reason(text=f"{who} is backed by {investors}", sources=rd.sources)
    text = f"{who}'s {rd.label or 'round'}"
    text += f" of {rd.amount_text}" if rd.amount_text else ""
    text += f" on {rd.date}" if rd.date else ""
    text += f"; investors: {investors}" if investors else ""
    return Reason(text=text, sources=rd.sources)


def _competitors(found: list[Competitor], company: str) -> list[Reason]:
    return [
        Reason(
            text=f"{c.company.name} is a direct competitor of {company}: {c.reason}",
            sources=c.company.sources,
        )
        for c in found
    ]


def _report(report: FounderReport) -> list[Reason]:
    company = report.company.name
    out = _competitors(report.competitors, company)
    for s in report.skip:
        out += [briefs.conflict_fact(c, s.investor.name, company) for c in s.conflicts]
    for i, s in enumerate(report.pitch, 1):
        # The rank and score are ours (computed), so this fact has no source of its own.
        out.append(
            Reason(
                text=f"{s.investor.name} is #{i} on the Pitch list for {company}: fit score "
                f"{s.score:g} of 100, no conflict found."
            )
        )
        out += [
            Reason(text=f"{s.investor.name}: {r.text}", sources=r.sources)
            for r in [*s.reasons, *s.warm_paths]
        ]
    return out


def facts(tool: str, args: dict, result: Any, names: dict[str, str]) -> list[Reason]:
    """A tool result as facts the agent can cite, each with at most its 3 best sources.
    `names` (id -> name) must already hold the entities in `args` and `result`."""

    def name(key: str) -> str:
        return names.get(args.get(key, ""), "the company")

    if tool == "find_competitors":
        out = _competitors(result, name("company_id"))
    elif tool == "get_rounds":
        out = [_round(rd, names) for rd in result]
    elif tool == "investor_profile":
        inv = result.investor
        out = [Reason(text=f"{inv.name}: {inv.description}", sources=inv.sources)]
        out += [_round(rd, names) for rd in result.rounds]
        out += [
            Reason(text=f"{inv.name} has backed {link.company.name}", sources=link.sources)
            for link in result.portfolio[:MAX_PORTFOLIO_FACTS]
        ]
    elif tool == "check_conflict":
        investor, company = name("investor_id"), name("company_id")
        out = [briefs.conflict_fact(c, investor, company) for c in result] or [
            # A computed "nothing found" has no source; the agent may still say it.
            Reason(
                text=f"No conflict found: nothing in Cala ties {investor} to a direct "
                f"competitor of {company}."
            )
        ]
    elif tool == "rank_investors":
        out = _report(result)
    elif tool == "sourced_answer":
        out = list(result)
    else:
        out = []
    return [briefs.best_sources(f) for f in out]
