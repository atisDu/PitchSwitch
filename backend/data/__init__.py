"""Data layer (Agent A). Everything outside this package gets its data from `get_store()`."""

from __future__ import annotations

from functools import lru_cache

from contracts.schemas import DataStore
from data.config import env_flag, load_env
from data.errors import DataError, NotFound, Upstream

__all__ = ["DataError", "NotFound", "Upstream", "get_store"]


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    """The store for this process: fixtures when USE_FAKE_STORE=true (the default), else Cala.

    Call `get_store.cache_clear()` after changing USE_FAKE_STORE in a test.
    """
    load_env()
    if env_flag("USE_FAKE_STORE", default=True):
        from data.fake_store import FakeDataStore

        return FakeDataStore()
    try:
        from data.store import CalaDataStore
    except ImportError as exc:  # the real store lands with tasks A6-A12
        raise NotImplementedError(
            "The real Cala store is not built yet (gate G2). Set USE_FAKE_STORE=true."
        ) from exc
    return CalaDataStore()
