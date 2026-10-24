"""Print the steps of the latest run for each given task: python scripts/show_run.py kth mergesort"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent import db  # noqa: E402

with db.connect() as c:
    for task in sys.argv[1:]:
        r = c.execute("select * from runs where task = %s order by started_at desc limit 1", (task,)).fetchone()
        print(f"===== {task} {r['run_id']} {r['status']} {r['guardrail'] or ''}")
        for s in c.execute("select n, node, detail from steps where run_id = %s order by id", (r["run_id"],)):
            d = s["detail"]
            if s["node"] == "tester":
                print(f"  {s['n']} tester passed={d.get('tests_passed')}\n    " + d.get("test_output", "")[-500:].replace("\n", "\n    "))
            elif s["node"] == "coder":
                print(f"  {s['n']} coder: {d.get('explanation', '')[:300]}")
            elif s["node"] == "researcher":
                print(f"  {s['n']} researcher calls={d.get('tool_calls')}\n    {d.get('findings', '')[:400]}")
            else:
                print(f"  {s['n']} {s['node']}: {json.dumps(d)[:200]}")
