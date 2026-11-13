"""Errors the data layer raises. B's API turns these into HTTP errors."""


class DataError(Exception):
    """Base class for data-layer errors."""


class NotFound(DataError, LookupError):
    """No entity with this ID. Raised by `company()`; list methods return [] instead."""


class Upstream(DataError):
    """Cala (or the cache) failed or is unreachable after retries."""
