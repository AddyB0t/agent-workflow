"""Run a candidate program against its tests inside an E2B cloud sandbox."""

import re
from dataclasses import dataclass
from pathlib import Path

from e2b_code_interpreter import Sandbox

from agent.config import settings
from agent.tasks import program_path, task_files, test_path
from agent.telemetry import tracer

REMOTE = "/home/user/repo"


@dataclass
class TestResult:
    passed: bool
    n_passed: int
    n_failed: int
    timed_out: bool
    output: str


def _counts(out: str) -> tuple[int, int]:
    p = re.search(r"(\d+) passed", out)
    f = re.search(r"(\d+) (failed|error)", out)
    return (int(p.group(1)) if p else 0, int(f.group(1)) if f else 0)


def run_tests(workspace: Path, task: str, candidate_code: str | None = None) -> TestResult:
    """Upload the task files (with `candidate_code` as the program, if given) and run pytest.

    A hard `timeout` wraps pytest because several buggy programs loop forever.
    """
    t = settings.sandbox_timeout_s
    with tracer.start_as_current_span("sandbox.run_tests") as span:
        span.set_attribute("task", task)
        with Sandbox.create(api_key=settings.e2b_api_key, timeout=t + 60) as sbx:
            for rel in task_files(task):
                content = (workspace / rel).read_text(encoding="utf-8")
                if rel == program_path(task) and candidate_code is not None:
                    content = candidate_code
                sbx.files.write(f"{REMOTE}/{rel}", content)
            sbx.files.write(f"{REMOTE}/python_programs/__init__.py", "")
            cmd = (
                f"cd {REMOTE} && timeout {t} python -m pytest -q -p no:cacheprovider "
                f"--tb=line -x {test_path(task)} > /tmp/out.txt 2>&1; "
                f"code=$?; tail -n 25 /tmp/out.txt; echo EXIT=$code"
            )
            r = sbx.commands.run(cmd, timeout=t + 30)
            out = (r.stdout or "") + (r.stderr or "")
        timed_out = "EXIT=124" in out
        n_pass, n_fail = _counts(out)
        passed = n_pass > 0 and n_fail == 0 and not timed_out
        span.set_attribute("passed", passed)
        span.set_attribute("timed_out", timed_out)
        if timed_out:
            out = f"[timed out after {t}s - likely an infinite loop]\n{out}"
        return TestResult(passed, n_pass, n_fail, timed_out, out[-3000:])
