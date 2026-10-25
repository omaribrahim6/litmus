from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "prepare_threshold": None},
            open=True,
        )
    return _pool


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    """A pooled connection inside a transaction (committed on success)."""
    with pool().connection() as conn:
        yield conn


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
