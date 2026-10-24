import os
import subprocess
import sys
from pathlib import Path

from agent.config import settings
from agent.graph import _guardrail, after_approval, after_reviewer, after_tester
from agent.tasks import TASKS, task_files


def base(**kw):
    return {"run_id": "t", "task": "gcd", "steps": 1, "tokens": 0, "cost": 0.0, "tool_calls": [], **kw}


def test_twenty_tasks_with_files_present():
    assert len(TASKS) == 20
    for t in TASKS:
        for rel in task_files(t):
            assert (settings.quixbugs / rel).exists(), rel


def test_step_cost_token_caps():
    assert _guardrail(base()) is None
    assert "step cap" in _guardrail(base(steps=settings.max_steps))
    assert "cost cap" in _guardrail(base(cost=settings.max_cost_usd))
    assert "token cap" in _guardrail(base(tokens=settings.max_tokens))


def test_loop_detection_on_repeated_identical_tool_call():
    call = 'read_file({"path": "python_programs/gcd.py"})'
    assert _guardrail(base(tool_calls=[call] * 2)) is None
    assert "loop detected" in _guardrail(base(tool_calls=[call] * 3))


def test_routing():
    assert after_tester(base(tests_passed=True)) == "reviewer"
    assert after_tester(base(tests_passed=False, attempts=1)) == "coder"
    assert after_tester(base(tests_passed=False, attempts=settings.max_fix_attempts)) == "finish"
    assert after_tester(base(tests_passed=True, guardrail="step cap")) == "finish"
    assert after_reviewer(base(review={"approve": True})) == "human_approval"
    assert after_reviewer(base(review={"approve": False}, attempts=1)) == "coder"
    assert after_approval(base(approved=False)) == "finish"
    assert after_approval(base(approved=True)) == "apply"


def test_files_server_blocks_path_escape(tmp_path: Path):
    code = (
        "import sys; sys.argv=['x']; import importlib.util as u;"
        f"s=u.spec_from_file_location('f', r'{Path('mcp_servers/files_server.py').resolve()}');"
        "m=u.module_from_spec(s); s.loader.exec_module(m);"
        "\ntry:\n    m.read_file('../secret.txt'); print('LEAK')\nexcept ValueError: print('BLOCKED')"
    )
    (tmp_path.parent / "secret.txt").write_text("x")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={**os.environ, "WORKSPACE_ROOT": str(tmp_path)})
    assert "BLOCKED" in out.stdout, out.stderr
