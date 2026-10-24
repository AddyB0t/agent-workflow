"""Start, resume and inspect workflow runs. Checkpoints live in Postgres (LangGraph PostgresSaver)."""

import uuid
from functools import lru_cache

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg.rows import dict_row

from agent import db
from agent.graph import build_graph
from agent.tasks import prepare_workspace
from agent.telemetry import tracer


@lru_cache(maxsize=1)
def graph():
    db.init_schema()
    conn = psycopg.connect(db.database_url(), autocommit=True, prepare_threshold=0, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()
    return build_graph(saver)


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}, "recursion_limit": 60}


def _outcome(run_id: str, result: dict) -> dict:
    pending = result.get("__interrupt__")
    if pending:
        return {"run_id": run_id, "status": "awaiting_approval", "approval": pending[0].value}
    return {"run_id": run_id, "status": result.get("status"), "guardrail": result.get("guardrail"),
            "steps": result.get("steps"), "cost": result.get("cost")}


def start(task: str, run_id: str | None = None) -> dict:
    run_id = run_id or f"{task}-{uuid.uuid4().hex[:8]}"
    ws = prepare_workspace(run_id, task)
    db.init_schema()
    db.start_run(run_id, task)
    with tracer.start_as_current_span("run.start") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("task", task)
        result = graph().invoke(
            {"run_id": run_id, "task": task, "workspace": str(ws), "steps": 0, "tokens": 0, "cost": 0.0,
             "attempts": 0, "tool_calls": [], "approvals_requested": 0},
            _config(run_id),
        )
    return _outcome(run_id, result)


def resume(run_id: str, approved: bool, by: str = "human") -> dict:
    with tracer.start_as_current_span("run.resume") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("approved", approved)
        result = graph().invoke(Command(resume={"approved": approved, "by": by}), _config(run_id))
    return _outcome(run_id, result)


def pending_approval(run_id: str) -> dict | None:
    snap = graph().get_state(_config(run_id))
    for t in snap.tasks:
        if t.interrupts:
            return t.interrupts[0].value
    return None
