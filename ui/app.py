"""Small web UI: start runs, watch steps live, approve or reject file writes.

Run: uv run uvicorn ui.app:app --port 8100
"""

import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agent import db, runner
from agent.tasks import TASKS

app = FastAPI(title="Agent Workflow")
_errors: dict[str, str] = {}


class StartRequest(BaseModel):
    task: str


class Decision(BaseModel):
    approved: bool


def _bg(run_id: str, fn, *args):
    def target():
        try:
            fn(*args)
        except Exception as e:  # surfaced in the UI instead of dying silently
            _errors[run_id] = repr(e)
            db.finish_run(run_id, status="error")
    threading.Thread(target=target, daemon=True).start()


@app.on_event("startup")
def _init():
    runner.graph()


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/api/tasks")
def tasks():
    return TASKS


@app.post("/api/runs")
def start(req: StartRequest):
    if req.task not in TASKS:
        raise HTTPException(400, "unknown task")
    run_id = f"{req.task}-{uuid.uuid4().hex[:8]}"
    _bg(run_id, runner.start, req.task, run_id)
    return {"run_id": run_id}


@app.get("/api/runs")
def runs():
    with db.connect() as c:
        return c.execute("select * from runs order by started_at desc limit 50").fetchall()


@app.get("/api/runs/{run_id}")
def run(run_id: str):
    with db.connect() as c:
        r = c.execute("select * from runs where run_id = %s", (run_id,)).fetchone()
        steps = c.execute("select n, node, detail, ts from steps where run_id = %s order by id", (run_id,)).fetchall()
    if not r:
        return {"run": {"run_id": run_id, "status": "starting"}, "steps": [], "approval": None}
    approval = runner.pending_approval(run_id) if r["status"] == "awaiting_approval" else None
    return {"run": r, "steps": steps, "approval": approval, "error": _errors.get(run_id)}


@app.post("/api/runs/{run_id}/decision")
def decide(run_id: str, d: Decision):
    if runner.pending_approval(run_id) is None:
        raise HTTPException(409, "run is not waiting for approval")
    _bg(run_id, runner.resume, run_id, d.approved, "web-ui")
    return {"ok": True}
