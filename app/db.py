"""Database engine factory.

Single switch between demo and production storage, controlled by the
DATABASE_URL env var:

  - Not set / empty:
        sqlite:///<repo>/data/tenders.db        (demo, local SQLite file)

  - Set to a SQLAlchemy URL:
        mssql+pyodbc://<user>:<pass>@<server>:1433/<db>?driver=ODBC+Driver+18+for+SQL+Server
        mssql+pyodbc://<server>:1433/<db>?driver=ODBC+Driver+18+for+SQL+Server&Authentication=ActiveDirectoryMsi
        postgresql+psycopg://<user>:<pass>@<host>/<db>
        ...

The same code path serves both backends. SQL syntax in app/storage.py is
currently SQLite-flavoured and works against SQLite directly; SQL Server
deployment may need small tweaks (e.g. INSERT OR REPLACE has no direct
T-SQL equivalent — pre-empt this in the deploy verification phase).
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .paths import DB_PATH

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the singleton SQLAlchemy engine, building it from env on first call."""
    global _engine
    if _engine is not None:
        return _engine

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        # Demo / local default — SQLite at the canonical data path
        url = f"sqlite:///{DB_PATH}"

    _engine = create_engine(url, pool_pre_ping=True, future=True)
    return _engine


def dialect_name() -> str:
    """Return the engine's dialect (e.g. 'sqlite', 'mssql', 'postgresql')."""
    return get_engine().dialect.name


class ConnWrapper:
    """Thin sqlite3-compatibility shim over a SQLAlchemy connection.

    Lets the existing app/storage.py code keep its sqlite3-style API
    (`conn.execute(sql, (a, b, c))`, `.fetchone()`, `.fetchall()`,
    `conn.commit()`, `conn.close()`) while actually running through
    SQLAlchemy. This way the same code talks to SQLite locally and
    to Azure SQL / PostgreSQL / etc. in production via DATABASE_URL.

    Translation rules:
      - `?` positional placeholders → `:p1, :p2, ...` named params
      - Tuple/list args            → dict for SQLAlchemy text()
      - Dict args                  → passed through
    """

    def __init__(self, sa_conn):
        self._c = sa_conn

    def execute(self, sql: str, params=()):
        bind = {}
        if params:
            if isinstance(params, dict):
                bind = params
            elif isinstance(params, (tuple, list)):
                parts = sql.split("?")
                if len(parts) - 1 != len(params):
                    raise ValueError(
                        f"placeholder mismatch: {len(parts)-1} '?' vs {len(params)} args"
                    )
                rebuilt = parts[0]
                for i, _v in enumerate(params, start=1):
                    rebuilt += f":p{i}" + parts[i]
                sql = rebuilt
                bind = {f"p{i+1}": v for i, v in enumerate(params)}
        # Return the raw Result so callers can use BOTH:
        #   row[0]                    (tuple-like, e.g. COUNT(*) queries)
        #   row._mapping["col"]       (dict-like access by column name)
        # Callers that want a dict should use `dict(row._mapping)` rather
        # than `dict(row)` — Row is tuple-like, not directly dict-castable.
        return self._c.execute(text(sql), bind)

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def get_db() -> ConnWrapper:
    """Return a sqlite3-compatible connection wrapper over the engine."""
    raw = get_engine().connect()
    # SQLite-only optimisation; harmless to skip on other dialects
    if dialect_name() == "sqlite":
        try:
            raw.execute(text("PRAGMA journal_mode=WAL"))
            raw.commit()
        except Exception:
            pass
    return ConnWrapper(raw)
