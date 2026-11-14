"""Pitchlist REST API (contracts/api.md).

resolve, founder/analyze, investor/check and brief run on core/. slush-prep and chat still replay
A's sample event streams from contracts/fixtures/models/ until B13-B14.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from agent import tools
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
    investor_names: list[str] = Field(min_length=1)


class ChatBody(BaseModel):
    company_id: str | None = None
    investor_id: str | None = None
    message: str = Field(min_length=1)


# --- fixture samples (replaced route by route as core lands) ------------------------------------


def _sample(name: str):
    path = MODELS_DIR / name
    if "/" in name or "\\" in name or not path.exists():  # ids end up in the file name
        raise HTTPException(404, f"no sample data for this request ({name})")
    return json.loads(path.read_text())


def _events(name: str) -> list[AgentEvent]:
    return [AgentEvent.model_validate(e) for e in _sample(name)]


def _sse(events: list[AgentEvent]) -> StreamingResponse:
    async def gen():
        for event in events:
            yield f"data: {event.model_dump_json()}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


_jobs: dict[str, list[AgentEvent]] = {}  # ponytail: in-memory, lost on restart; fine for a demo


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
    job_id = uuid.uuid4().hex
    _jobs[job_id] = _events("agent_events_slush_prep.json")
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str) -> StreamingResponse:
    if job_id not in _jobs:
        raise HTTPException(404, f"no job {job_id}")
    return _sse(_jobs[job_id])


@app.post("/api/chat")
async def chat(body: ChatBody) -> StreamingResponse:
    return _sse(_events("agent_events_chat.json"))
