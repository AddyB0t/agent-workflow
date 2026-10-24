"""The multi-agent workflow as a LangGraph state graph.

planner -> researcher -> coder -> tester --pass--> reviewer --ok--> human_approval -> apply -> finish
                           ^        |fail                 |changes
                           +--------+---------------------+
Every edge first checks the guardrails (steps, tokens, cost, loops) and jumps to `finish` if one trips.
"""

import difflib
import json
import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agent import db
from agent.config import settings
from agent.mcp_hub import hub
from agent.sandbox import run_tests
from agent.tasks import program_path, task_prompt, test_path
from agent.telemetry import tracer


class State(TypedDict, total=False):
    run_id: str
    task: str
    workspace: str
    plan: list[str]
    findings: str
    original: str
    candidate: str
    explanation: str
    test_output: str
    tests_passed: bool
    attempts: int
    review: dict
    approved: bool
    status: str
    guardrail: str | None
    steps: int
    tokens: int
    cost: float
    tool_calls: Annotated[list[str], operator.add]
    approvals_requested: int


# ---------- helpers ----------

def _llm(json_mode: bool = False):
    llm = ChatOpenAI(model=settings.llm_model, base_url=settings.llm_base_url, api_key=settings.llm_api_key,
                     temperature=0, timeout=90, max_retries=2)
    return llm.bind(response_format={"type": "json_object"}) if json_mode else llm


def _account(state: State, node: str, msg: AIMessage) -> dict:
    u = msg.usage_metadata or {}
    pin, pout = u.get("input_tokens", 0), u.get("output_tokens", 0)
    p_in, p_out = settings.price()
    usd = pin / 1e6 * p_in + pout / 1e6 * p_out
    db.log_cost(state["run_id"], node, pin, pout, usd)
    return {"tokens": state.get("tokens", 0) + pin + pout, "cost": state.get("cost", 0.0) + usd}


def _guardrail(state: State) -> str | None:
    if state.get("guardrail"):
        return state["guardrail"]
    if state.get("steps", 0) >= settings.max_steps:
        return f"step cap ({settings.max_steps})"
    if state.get("cost", 0.0) >= settings.max_cost_usd:
        return f"cost cap (${settings.max_cost_usd})"
    if state.get("tokens", 0) >= settings.max_tokens:
        return f"token cap ({settings.max_tokens})"
    calls = state.get("tool_calls", [])
    for c in set(calls):
        if calls.count(c) >= settings.loop_repeat_limit:
            return f"loop detected: {c[:80]} called {settings.loop_repeat_limit} times"
    return None


def node(name: str):
    """Wrap a node: count the step, trace it, log it to Postgres, and stop early on guardrails."""
    def deco(fn):
        def wrapper(state: State) -> dict:
            steps = state.get("steps", 0) + 1
            with tracer.start_as_current_span(f"node.{name}") as span:
                span.set_attribute("run_id", state["run_id"])
                span.set_attribute("step", steps)
                update = fn({**state, "steps": steps}) or {}
                update["steps"] = update.get("steps", steps)
                merged = {**state, **update, "tool_calls": state.get("tool_calls", []) + update.get("tool_calls", [])}
                trip = _guardrail(merged) if name != "finish" else None
                if trip and not merged.get("guardrail"):
                    update["guardrail"] = trip
                    span.set_attribute("guardrail", trip)
            detail = {k: v for k, v in update.items() if k not in ("original",)}
            for k in ("candidate", "test_output", "findings"):
                if k in detail:
                    detail[k] = str(detail[k])[:1500]
            db.log_step(state["run_id"], update["steps"], name, detail)
            db.update_run(state["run_id"], steps=update["steps"], tokens=merged.get("tokens", 0),
                          cost_usd=merged.get("cost", 0.0))
            return update
        wrapper.__name__ = name
        return wrapper
    return deco


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


# ---------- nodes ----------

@node("planner")
def planner(state: State) -> dict:
    msg = _llm(json_mode=True).invoke([
        SystemMessage("You are the planner in a bug-fixing team (planner, researcher, coder, reviewer). "
                      'Return JSON {"steps": [short imperative steps]} with 3-5 steps.'),
        HumanMessage(task_prompt(state["task"])),
    ])
    plan = _parse_json(msg.content).get("steps", [])
    return {"plan": plan, **_account(state, "planner", msg)}


def _research_tools(state: State):
    run, h = state["run_id"], hub()

    @tool
    def list_files() -> str:
        """List the files in the repository."""
        return h.call("list_files", {"path": run}).replace(f"{run}/", "")

    @tool
    def read_file(path: str) -> str:
        """Read a repository file, e.g. python_programs/x.py."""
        return h.call("read_file", {"path": f"{run}/{path}"})

    @tool
    def web_search(query: str) -> str:
        """Search the web for algorithm descriptions or documentation."""
        return h.call("web_search", {"query": query, "max_results": 4})

    @tool
    def fetch_page(url: str) -> str:
        """Open a web page in a headless browser and return its text."""
        return h.call("fetch_page", {"url": url, "max_chars": 3000})

    @tool
    def recall_memory() -> str:
        """Notes from earlier runs on this same task."""
        return h.call("recall_memory", {"task": state["task"]})

    return [list_files, read_file, web_search, fetch_page, recall_memory]


@node("researcher")
def researcher(state: State) -> dict:
    tools = _research_tools(state)
    by_name = {t.name: t for t in tools}
    llm = _llm().bind_tools(tools)
    messages = [
        SystemMessage(
            "You are the researcher. Use the tools to read the program and its tests, and look up the intended "
            "algorithm on the web if useful. Use at most 6 tool calls. Then reply (no tool call) with: the bug "
            "location (line), why it is wrong, and the intended behaviour. Do not write the fixed file."
        ),
        HumanMessage(f"{task_prompt(state['task'])}\nPlan: {state.get('plan')}"),
    ]
    acct = {"tokens": state.get("tokens", 0), "cost": state.get("cost", 0.0)}
    calls: list[str] = []
    for _ in range(7):
        msg = llm.invoke(messages)
        acct = _account({**state, **acct}, "researcher", msg)
        messages.append(msg)
        if not msg.tool_calls:
            break
        for tc in msg.tool_calls:
            key = f"{tc['name']}({json.dumps(tc['args'], sort_keys=True)})"
            calls.append(key)
            if calls.count(key) >= settings.loop_repeat_limit:
                return {"tool_calls": calls, "findings": "", **acct}
            out = by_name[tc["name"]].invoke(tc["args"]) if tc["name"] in by_name else "unknown tool"
            messages.append(ToolMessage(content=str(out)[:4000], tool_call_id=tc["id"]))
    else:
        messages.append(HumanMessage("Tool budget used up. Give your findings now."))
        msg = _llm().invoke(messages)
        acct = _account({**state, **acct}, "researcher", msg)
    original = hub().call("read_file", {"path": f"{state['run_id']}/{program_path(state['task'])}"})
    return {"findings": msg.content, "original": original, "tool_calls": calls, **acct}


@node("coder")
def coder(state: State) -> dict:
    feedback = ""
    if state.get("attempts", 0) > 0:
        feedback = (
            f"\n\nAttempt {state['attempts']} FAILED. This was your patch:\n```diff\n{_diff(state)}\n```\n"
            f"Test output:\n{state.get('test_output', '')[-1500:]}\n"
            f"Reviewer: {state.get('review', {}).get('comments', '')}\n"
            "Do NOT resubmit the same change. The research findings may be wrong: re-read the original code, "
            "trace the failing test input by hand, and form a different hypothesis about which line is buggy."
        )
    msg = _llm(json_mode=True).invoke([
        SystemMessage("You are the coder. Fix the bug with the smallest possible change; keep the docstring. "
                      "First reason step by step: trace a small example through the original code and compare it "
                      "with the intended algorithm. "
                      'Return JSON {"analysis": "<your trace>", "explanation": "<one or two sentences>", '
                      '"code": "<the complete fixed file>"}.'),
        HumanMessage(f"{task_prompt(state['task'])}\n\nResearch findings:\n{state.get('findings', '')}\n\n"
                     f"Current file {program_path(state['task'])}:\n```python\n{state['original']}\n```{feedback}"),
    ])
    data = _parse_json(msg.content)
    return {"candidate": data.get("code", ""), "explanation": data.get("explanation", ""),
            "attempts": state.get("attempts", 0) + 1, **_account(state, "coder", msg)}


@node("tester")
def tester(state: State) -> dict:
    from pathlib import Path

    res = run_tests(Path(state["workspace"]), state["task"], state["candidate"])
    return {"tests_passed": res.passed, "test_output": res.output}


def _diff(state: State) -> str:
    p = program_path(state["task"])
    return "".join(difflib.unified_diff(
        state["original"].splitlines(keepends=True), state["candidate"].splitlines(keepends=True),
        fromfile=f"a/{p}", tofile=f"b/{p}",
    ))


@node("reviewer")
def reviewer(state: State) -> dict:
    diff = _diff(state)
    msg = _llm(json_mode=True).invoke([
        SystemMessage("You are the code reviewer. Approve only if the diff is a minimal, correct fix of the bug, "
                      "does not special-case test inputs, and does not touch unrelated code. "
                      'Return JSON {"approve": true|false, "comments": "..."}.'),
        HumanMessage(f"Task: {task_prompt(state['task'])}\nTests in sandbox: PASSED\n\nDiff:\n{diff}"),
    ])
    review = _parse_json(msg.content)
    return {"review": {"approve": bool(review.get("approve")), "comments": review.get("comments", ""), "diff": diff},
            **_account(state, "reviewer", msg)}


@node("human_approval")
def human_approval(state: State) -> dict:
    n = state.get("approvals_requested", 0) + 1
    db.update_run(state["run_id"], status="awaiting_approval", approvals_requested=n)
    decision: Any = interrupt({
        "action": f"write_file {program_path(state['task'])}",
        "diff": state["review"]["diff"],
        "explanation": state.get("explanation", ""),
        "reviewer": state["review"]["comments"],
    })
    approved = bool(decision.get("approved"))
    db.log_approval(state["run_id"], "approved" if approved else "rejected", decision.get("by", "human"),
                    state["review"]["diff"])
    db.update_run(state["run_id"], status="running")
    return {"approved": approved, "approvals_requested": n}


@node("apply")
def apply(state: State) -> dict:
    out = hub().call("write_file", {"path": f"{state['run_id']}/{program_path(state['task'])}",
                                    "content": state["candidate"]})
    return {"status": "passed" if out.startswith("wrote") else "failed"}


@node("finish")
def finish(state: State) -> dict:
    if state.get("guardrail"):
        status = "stopped"
    elif state.get("approved") is False:
        status = "rejected"
    else:
        status = state.get("status") or "failed"
    note = (f"{status}: {state.get('explanation') or state.get('findings', '')[:300]}"
            if status in ("passed", "failed") else f"{status}: {state.get('guardrail') or ''}")
    db.add_memory(state["task"], note[:500])
    db.finish_run(state["run_id"], status=status, guardrail=state.get("guardrail"),
                  approved=state.get("approved"))
    return {"status": status}


# ---------- routing ----------

def _route(next_node: str):
    def route(state: State) -> str:
        return "finish" if state.get("guardrail") else next_node
    return route


def after_tester(state: State) -> str:
    if state.get("guardrail"):
        return "finish"
    if state.get("tests_passed"):
        return "reviewer"
    return "coder" if state.get("attempts", 0) < settings.max_fix_attempts else "finish"


def after_reviewer(state: State) -> str:
    if state.get("guardrail"):
        return "finish"
    if state["review"]["approve"]:
        return "human_approval"
    return "coder" if state.get("attempts", 0) < settings.max_fix_attempts else "finish"


def after_approval(state: State) -> str:
    return "apply" if state.get("approved") and not state.get("guardrail") else "finish"


def build_graph(checkpointer):
    g = StateGraph(State)
    for fn in (planner, researcher, coder, tester, reviewer, human_approval, apply, finish):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", _route("researcher"), ["researcher", "finish"])
    g.add_conditional_edges("researcher", _route("coder"), ["coder", "finish"])
    g.add_conditional_edges("coder", _route("tester"), ["tester", "finish"])
    g.add_conditional_edges("tester", after_tester, ["reviewer", "coder", "finish"])
    g.add_conditional_edges("reviewer", after_reviewer, ["human_approval", "coder", "finish"])
    g.add_conditional_edges("human_approval", after_approval, ["apply", "finish"])
    g.add_edge("apply", "finish")
    g.add_edge("finish", END)
    return g.compile(checkpointer=checkpointer)
