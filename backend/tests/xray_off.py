"""Autouse for B's tests (core, api, agent, mcp_server): no network from B22 or B23.

- B22's portfolio X-ray calls Gemini for every portfolio company never judged. Here it judges
  nothing (no hidden rivals, no thesis), and the verdicts memo is cleared between tests. A test
  of the X-ray restores the real one: `monkeypatch.setattr(xray, "portfolio_verdicts", real)`.
- B23's fresh funds and lead partners ask Cala's search and Gemini: here there are none. A
  test of B23 patches `core.scoring.fresh_funds` / `lead_partner` itself.
- On the fake store (the default) the shared graph is in memory, so a test never opens MongoDB
  Atlas from .env (scoring's closeness reads it). A live run (USE_FAKE_STORE=false, B9) keeps
  the real graph.
"""

import os

import pytest

import core.competitors as competitors
import core.fresh as fresh
import core.scoring as scoring
import core.xray as xray
from cache.graph import MemoryGraph


@pytest.fixture(autouse=True)
def xray_off(monkeypatch):
    async def judged_nothing(company, refs, graph=None):
        return {}

    monkeypatch.setattr(xray, "portfolio_verdicts", judged_nothing)
    monkeypatch.setattr(competitors, "_verdict_memo", {})

    async def no_funds(sector, today=None):
        return []

    async def no_partner(investor, sector, look_up=True, deals=()):
        return None

    async def no_notes(company, competitors):
        return []

    monkeypatch.setattr(scoring, "report_notes", no_notes)  # B24 asks Cala's search and Gemini
    monkeypatch.setattr(scoring, "fresh_funds", no_funds)
    monkeypatch.setattr(scoring, "lead_partner", no_partner)
    monkeypatch.setattr(fresh, "lead_partner", no_partner)  # stored_partner_conflicts
    if os.environ.get("USE_FAKE_STORE", "true").strip().lower() != "false":
        monkeypatch.setattr(competitors, "_graph", MemoryGraph())
