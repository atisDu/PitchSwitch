"""Pitchlist REST API (contracts/api.md).

resolve, founder/analyze, investor/check and brief run on core/; slush-prep runs the Gemini agent
(agent/gemini_agent.py). chat still replays A's sample event stream until B14.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent import gemini_agent, tools
from agent.llm import LLMError
from contracts.schemas import (
    CONTRACT_VERSION,
    AgentEvent,
    Brief,
    Company,
    Competitor,
    EntityRef,
    FounderReport,
    InvestorCheck,
)
from core.competitors import Judgement, stored_judgement
from core.conflict import check_conflict
from core.scoring import rank_investors
from data import NotFound, Upstream, get_store
from data.config import MODELS_DIR

MAX_SLUSH_INVESTORS = 25  # one Gemini loop and one brief each

app = FastAPI(title="Pitchlist API", version=CONTRACT_VERSION)
# ponytail: any origin, no credentials; pin to the deployed frontend URL if that ever matters.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- errors: always {error: string} -----------------------------------------------------------


@app.exception_handler(StarletteHTTPException)  # also unknown routes / wrong methods
async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse({"error": str(exc.detail)}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    msg = "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors())
    return JSONResponse({"error": msg or "invalid request"}, status_code=422)


@app.exception_handler(NotFound)
async def _not_found(_: Request, exc: NotFound) -> JSONResponse:
    return JSONResponse({"error": str(exc) or "not found"}, status_code=404)


@app.exception_handler(Upstream)
async def _upstream(_: Request, exc: Upstream) -> JSONResponse:
    return JSONResponse({"error": f"data source unavailable: {exc}"}, status_code=502)


@app.exception_handler(LLMError)
async def _llm(_: Request, exc: LLMError) -> JSONResponse:
    return JSONResponse({"error": f"competitor judging unavailable: {exc}"}, status_code=503)


def _replay(name: str) -> AsyncIterator[AgentEvent]:
    events = [AgentEvent.model_validate(e) for e in json.loads((MODELS_DIR / name).read_text())]

    async def gen():
        for event in events:
            yield event

    return gen()


# --- request bodies -----------------------------------------------------------------------------


class ResolveBody(BaseModel):
    name: str = Field(min_length=1)
    kind: Literal["company", "investor"]


class FounderBody(BaseModel):
    company_id: str = Field(min_length=1)
    competitor_ids: list[str] | None = None


class PairBody(BaseModel):
    investor_id: str = Field(min_length=1)
    company_id: str = Field(min_length=1)


class SlushPrepBody(BaseModel):
    company_id: str = Field(min_length=1)
    investor_names: list[str] = Field(min_length=1, max_length=MAX_SLUSH_INVESTORS)


class ChatBody(BaseModel):
    company_id: str | None = None
    investor_id: str | None = None
    message: str = Field(min_length=1)


# --- streams ------------------------------------------------------------------------------------


def _sse(events: AsyncIterator[AgentEvent]) -> StreamingResponse:
    async def gen():
        async for event in events:
            yield f"data: {event.model_dump_json()}\n\n"

    # A proxy in front (the deployed HTTPS one) must pass events on as they come, unbuffered.
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


# Slush-prep jobs: the events so far, appended to by the job's task.
# ponytail: in memory, never evicted, lost on restart; fine for a demo.
_jobs: dict[str, list[AgentEvent]] = {}
_tasks: set[asyncio.Task] = set()  # keeps running jobs from being garbage-collected


# --- routes -------------------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "contract_version": CONTRACT_VERSION}


@app.post("/api/resolve")
async def resolve(body: ResolveBody) -> list[EntityRef]:
    return await get_store().resolve(body.name, body.kind)


async def _chosen(company: Company, ids: list[str], judged: Judgement) -> list[Competitor]:
    """Exactly the competitors the user kept, with the judge's reason where it gave one."""
    known = {c.company.id: c for c in judged.direct}
    space = {c.id: c for c in judged.space}
    out = []
    for i in dict.fromkeys(ids):
        if i in known:
            out.append(known[i])
        elif i != company.id:
            other = space.get(i) or await get_store().company(i)
            out.append(Competitor(company=other, reason="Chosen by you"))
    return out


@app.post("/api/founder/analyze")
async def founder_analyze(body: FounderBody) -> FounderReport:
    company = await get_store().company(body.company_id)
    judged = await stored_judgement(company)
    if body.competitor_ids is None:
        competitors = judged.direct
    else:
        competitors = await _chosen(company, body.competitor_ids, judged)
    space = [*(c.company for c in judged.direct), *judged.space]  # a removed rival stays in space
    return await rank_investors(company, competitors, space)


@app.post("/api/investor/check")
async def investor_check(body: PairBody) -> InvestorCheck:
    store = get_store()
    investor, company = await asyncio.gather(
        store.company(body.investor_id), store.company(body.company_id)
    )
    competitors = (await stored_judgement(company)).direct
    conflicts, *round_lists = await asyncio.gather(
        check_conflict(investor.id, competitors),
        *(store.rounds(i) for i in [company.id, *(c.company.id for c in competitors)]),
    )
    return InvestorCheck(
        investor=EntityRef(**investor.model_dump(include={"id", "name", "type", "description"})),
        company=company,
        conflicts=conflicts,
        competitors=competitors,
        rounds=[rd for rounds in round_lists for rd in rounds],
    )


@app.post("/api/brief")
async def brief(body: PairBody) -> Brief:
    return await tools.investor_brief(body.investor_id, body.company_id)


@app.post("/api/slush-prep")
async def slush_prep(body: SlushPrepBody) -> dict:
    company = await get_store().company(body.company_id)  # unknown company: 404 now, not later
    job_id = uuid.uuid4().hex
    events = _jobs[job_id] = []

    async def work() -> None:
        async for event in gemini_agent.slush_prep(company, body.investor_names):
            events.append(event)

    task = asyncio.create_task(work())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str) -> StreamingResponse:
    """Every event of the job from its start, then the new ones as they come: opening the stream
    twice (a reconnect, React's double effect) replays; it never runs the job again."""
    if job_id not in _jobs:
        raise HTTPException(404, f"no job {job_id}")
    events = _jobs[job_id]

    async def follow():
        sent = 0
        while True:
            for event in events[sent:]:
                sent += 1
                yield event
                if event.type == "done":
                    return
            await asyncio.sleep(0.2)  # ponytail: polling; an asyncio.Condition if 0.2 s ever shows

    return _sse(follow())


@app.post("/api/chat")
async def chat(body: ChatBody) -> StreamingResponse:
    return _sse(_replay("agent_events_chat.json"))  # until B14
