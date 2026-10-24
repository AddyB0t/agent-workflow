"""Run all 20 QuixBugs tasks and report success rate, steps, cost, time, approvals and guardrail stops.

Approval policy during evaluation: the human-approval interrupt still fires on every run, and an
automatic approver says yes (logged as `eval-auto-approver`). After a fix is written, the repo file is
re-tested in a fresh E2B sandbox as an independent check.

Usage: python eval/run_eval.py [--workers 4] [--tasks a,b,c]
"""

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import db, runner  # noqa: E402
from agent.config import settings  # noqa: E402
from agent.sandbox import run_tests  # noqa: E402
from agent.tasks import TASKS  # noqa: E402

OUT = Path(__file__).parent / "results"


def run_one(task: str) -> dict:
    t0 = time.time()
    try:
        out = runner.start(task)
        while out["status"] == "awaiting_approval":
            out = runner.resume(out["run_id"], True, by="eval-auto-approver")
    except Exception as e:
        return {"task": task, "status": "error", "error": repr(e), "seconds": round(time.time() - t0, 1)}
    run_id = out["run_id"]
    with db.connect() as c:
        r = c.execute("select * from runs where run_id = %s", (run_id,)).fetchone()
    verified = None
    if r["status"] == "passed":
        verified = run_tests(settings.workspace / run_id, task).passed
    row = {
        "task": task, "run_id": run_id, "status": r["status"], "guardrail": r["guardrail"],
        "steps": r["steps"], "tokens": r["tokens"], "cost_usd": round(r["cost_usd"], 5),
        "approvals_requested": r["approvals_requested"], "verified_after_apply": verified,
        "seconds": round(time.time() - t0, 1),
    }
    print(json.dumps(row), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tasks", default=",".join(TASKS))
    args = ap.parse_args()
    runner.graph()
    tasks = args.tasks.split(",")
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(run_one, tasks))

    OUT.mkdir(exist_ok=True)
    (OUT / "runs.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    ok = [r for r in rows if r["status"] == "passed" and r.get("verified_after_apply")]
    summary = {
        "llm_model": settings.llm_model,
        "tasks": len(rows),
        "success": len(ok),
        "success_rate": round(len(ok) / len(rows), 3),
        "status_counts": {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})},
        "avg_steps": round(statistics.mean(r.get("steps") or 0 for r in rows), 2),
        "avg_cost_usd": round(statistics.mean(r.get("cost_usd") or 0 for r in rows), 5),
        "total_cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 4),
        "avg_seconds": round(statistics.mean(r["seconds"] for r in rows), 1),
        "approvals_requested": sum(r.get("approvals_requested") or 0 for r in rows),
        "guardrail_stops": sum(bool(r.get("guardrail")) for r in rows),
        "guardrails": {"max_steps": settings.max_steps, "max_cost_usd": settings.max_cost_usd,
                       "max_tokens": settings.max_tokens, "sandbox_timeout_s": settings.sandbox_timeout_s,
                       "max_fix_attempts": settings.max_fix_attempts, "loop_repeat_limit": settings.loop_repeat_limit},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = ["# Evaluation: 20 QuixBugs tasks", "", f"Model `{settings.llm_model}`.", "",
             "| Task | Status | Steps | Cost (USD) | Seconds | Approvals | Verified | Guardrail |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['task']} | {r['status']} | {r.get('steps')} | {r.get('cost_usd')} | {r['seconds']} | "
                     f"{r.get('approvals_requested')} | {r.get('verified_after_apply')} | {r.get('guardrail') or ''} |")
    lines += ["", "```json", json.dumps(summary, indent=2), "```"]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
