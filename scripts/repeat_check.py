"""For failed runs in a results file, count how many distinct patches the coder produced."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import db  # noqa: E402

path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/runs.jsonl")
rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
with db.connect() as c:
    for r in rows:
        if r["status"] == "passed":
            continue
        cands = [s["detail"].get("candidate") for s in c.execute(
            "select detail from steps where run_id = %s and node = 'coder' order by id", (r["run_id"],))]
        print(f"{r['task']:18s} {r['status']:8s} attempts={len(cands)} distinct_patches={len(set(cands))}")
