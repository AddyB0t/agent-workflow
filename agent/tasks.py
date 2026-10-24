"""QuixBugs tasks: each is one Python program with a one-line bug and a pytest suite."""

import shutil
from pathlib import Path

from agent.config import settings

TASKS = [
    "bitcount", "bucketsort", "find_first_in_sorted", "find_in_sorted", "flatten",
    "gcd", "get_factors", "hanoi", "is_valid_parenthesization", "kheapsort",
    "kth", "lis", "max_sublist_sum", "mergesort", "next_palindrome",
    "pascal", "possible_change", "powerset", "quicksort", "sieve",
]


def program_path(task: str) -> str:
    return f"python_programs/{task}.py"


def test_path(task: str) -> str:
    return f"python_testcases/test_{task}.py"


def task_files(task: str) -> list[str]:
    """Repo-relative files needed to run one task's tests."""
    return [
        program_path(task),
        test_path(task),
        "python_testcases/load_testdata.py",
        f"json_testcases/{task}.json",
        "conftest.py",
    ]


def prepare_workspace(run_id: str, task: str) -> Path:
    """Copy the buggy program and its tests into an isolated working repo for this run."""
    if task not in TASKS:
        raise ValueError(f"Unknown task {task!r}")
    ws = settings.workspace / run_id
    for rel in task_files(task):
        dest = ws / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(settings.quixbugs / rel, dest)
    (ws / "python_programs" / "__init__.py").touch()
    return ws


def task_prompt(task: str) -> str:
    return (
        f"The program `{program_path(task)}` contains a bug, so its tests in "
        f"`{test_path(task)}` fail. Find the bug and fix it with the smallest change. "
        "Do not edit the tests."
    )
