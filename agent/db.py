"""Postgres: run history, steps, approvals, costs and long-term memory.

If DATABASE_URL is empty, an embedded Postgres (pgserver) is started under ./.pgdata.
"""

import json
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row

from agent.config import settings

SCHEMA = """
create table if not exists runs (
    run_id text primary key,
    task text not null,
    status text not null default 'running',
    guardrail text,
    steps int default 0,
    tokens int default 0,
    cost_usd double precision default 0,
    approvals_requested int default 0,
    approved boolean,
    started_at timestamptz default now(),
    ended_at timestamptz
);
create table if not exists steps (
    id bigserial primary key,
    run_id text references runs(run_id),
    n int,
    node text,
    detail jsonb,
    ts timestamptz default now()
);
create table if not exists approvals (
    id bigserial primary key,
    run_id text references runs(run_id),
    decision text,
    decided_by text,
    diff text,
    ts timestamptz default now()
);
create table if not exists costs (
    id bigserial primary key,
    run_id text references runs(run_id),
    node text,
    prompt_tokens int,
    completion_tokens int,
    usd double precision,
    ts timestamptz default now()
);
create table if not exists memory (
    id bigserial primary key,
    task text,
    note text,
    ts timestamptz default now()
);
"""


@lru_cache(maxsize=1)
def database_url() -> str:
    if settings.database_url:
        return settings.database_url
    import pgserver

    settings.pgdata.mkdir(parents=True, exist_ok=True)
    server = pgserver.get_server(str(settings.pgdata), cleanup_mode=None)
    return server.get_uri()


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), autocommit=True, row_factory=dict_row)


def init_schema():
    with connect() as c:
        c.execute(SCHEMA)


def start_run(run_id: str, task: str):
    with connect() as c:
        c.execute("insert into runs (run_id, task) values (%s, %s) on conflict do nothing", (run_id, task))


def log_step(run_id: str, n: int, node: str, detail: dict):
    with connect() as c:
        c.execute(
            "insert into steps (run_id, n, node, detail) values (%s, %s, %s, %s)",
            (run_id, n, node, json.dumps(detail, default=str)),
        )


def log_cost(run_id: str, node: str, prompt: int, completion: int, usd: float):
    with connect() as c:
        c.execute(
            "insert into costs (run_id, node, prompt_tokens, completion_tokens, usd) values (%s,%s,%s,%s,%s)",
            (run_id, node, prompt, completion, usd),
        )


def log_approval(run_id: str, decision: str, by: str, diff: str):
    with connect() as c:
        c.execute(
            "insert into approvals (run_id, decision, decided_by, diff) values (%s,%s,%s,%s)",
            (run_id, decision, by, diff),
        )


def finish_run(run_id: str, **fields):
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    with connect() as c:
        c.execute(f"update runs set {sets}, ended_at = now() where run_id = %(run_id)s", {**fields, "run_id": run_id})


def update_run(run_id: str, **fields):
    sets = ", ".join(f"{k} = %({k})s" for k in fields)
    with connect() as c:
        c.execute(f"update runs set {sets} where run_id = %(run_id)s", {**fields, "run_id": run_id})


def add_memory(task: str, note: str):
    with connect() as c:
        c.execute("insert into memory (task, note) values (%s, %s)", (task, note))
