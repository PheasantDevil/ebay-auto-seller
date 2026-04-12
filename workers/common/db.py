from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus

import psycopg


@lru_cache(maxsize=8)
def _secret_json(secret_arn: str) -> dict[str, Any]:
    import boto3

    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=secret_arn)
    return json.loads(resp["SecretString"])


def _database_url_from_aurora_env() -> str | None:
    arn = os.environ.get("AURORA_SECRET_ARN")
    host = os.environ.get("PGHOST")
    if not arn or not host:
        return None
    port = os.environ.get("PGPORT", "5432")
    database = os.environ.get("PGDATABASE", "ebayautoseller")
    data = _secret_json(arn)
    user = str(data.get("username") or "dbadmin")
    password = str(data["password"])
    return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{database}"


def connect() -> psycopg.Connection:
    database_url = os.environ.get("DATABASE_URL") or _database_url_from_aurora_env()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set, and AURORA_SECRET_ARN / PGHOST are incomplete."
        )

    connect_timeout_sec = int(os.environ.get("DB_CONNECT_TIMEOUT_SEC", "5"))
    statement_timeout_ms = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS", "5000"))

    return psycopg.connect(
        database_url,
        connect_timeout=connect_timeout_sec,
        options=f"-c statement_timeout={statement_timeout_ms}",
    )
