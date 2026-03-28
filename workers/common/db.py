from __future__ import annotations

import os

import psycopg


def connect() -> psycopg.Connection:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set.")

    connect_timeout_sec = int(os.environ.get("DB_CONNECT_TIMEOUT_SEC", "5"))
    statement_timeout_ms = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "5000"))

    return psycopg.connect(
        database_url,
        connect_timeout=connect_timeout_sec,
        options=f"-c statement_timeout={statement_timeout_ms}",
    )
