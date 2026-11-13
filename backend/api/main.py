"""Pitchlist REST API (contracts/api.md).

B1 skeleton: /api/resolve uses the store; the other routes serve A's sample fixtures from
contracts/fixtures/models/ until core lands (B7 founder/check, B11 brief, B13-B14 agent).
"""

from __future__ import annotations

import json
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from contracts.schemas import (
    CONTRACT_VERSION,
    AgentEvent,
    Brief,
    EntityRef,
    FounderReport,
    InvestorCheck,
)
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


def _canonical(entity_id: str) -> str:
    """Cala has several IDs for one firm; fixtures are keyed by the main one."""
    return (_sample("index.json").get("aliases") or {}).get(entity_id, entity_id)


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


@app.post("/api/founder/analyze")
async def founder_analyze(body: FounderBody) -> FounderReport:
    return _sample(f"founder_report_{_canonical(body.company_id)}.json")


@app.post("/api/investor/check")
async def investor_check(body: PairBody) -> InvestorCheck:
    inv, co = _canonical(body.investor_id), _canonical(body.company_id)
    return _sample(f"investor_check_{inv}_{co}.json")


@app.post("/api/brief")
async def brief(body: PairBody) -> Brief:
    inv, co = _canonical(body.investor_id), _canonical(body.company_id)
    return _sample(f"brief_{inv}_{co}.json")


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
