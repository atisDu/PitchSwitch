"""Autouse for B's tests (core, api, agent, mcp_server): no network from the B22 X-ray.

- B22's portfolio X-ray calls Gemini for every portfolio company never judged. Here it judges
  nothing (no hidden rivals, no thesis), and the verdicts memo is cleared between tests. A test
  of the X-ray restores the real one: `monkeypatch.setattr(xray, "portfolio_verdicts", real)`.
- On the fake store (the default) the shared graph is in memory, so a test never opens MongoDB
  Atlas from .env (scoring's closeness reads it). A live run (USE_FAKE_STORE=false, B9) keeps
  the real graph.
"""

import os

import pytest

import core.competitors as competitors
import core.xray as xray
from cache.graph import MemoryGraph


@pytest.fixture(autouse=True)
def xray_off(monkeypatch):
    async def judged_nothing(company, refs, graph=None):
        return {}

    monkeypatch.setattr(xray, "portfolio_verdicts", judged_nothing)
    monkeypatch.setattr(competitors, "_verdict_memo", {})
    if os.environ.get("USE_FAKE_STORE", "true").strip().lower() != "false":
        monkeypatch.setattr(competitors, "_graph", MemoryGraph())
