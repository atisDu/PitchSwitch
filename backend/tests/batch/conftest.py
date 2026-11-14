"""Shared test helpers for the batch job."""

import pytest


@pytest.fixture(autouse=True)
def no_real_services(monkeypatch):
    """Tests never reach MongoDB Atlas, whatever .env says."""
    monkeypatch.setenv("MONGODB_URI", "")
