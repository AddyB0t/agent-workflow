"""Keeps one stdio session open to each MCP server on a background event loop,
so the (synchronous) LangGraph nodes can call MCP tools with a plain function call."""

import asyncio
import json
import os
import sys
import threading
from contextlib import AsyncExitStack
from functools import lru_cache

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from agent.config import ROOT, settings
from agent.db import database_url
from agent.telemetry import tracer

SERVERS = ("files", "search", "browser", "db")


def _text(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, list):
        parts = [b.get("text", "") if isinstance(b, dict) else str(getattr(b, "text", b)) for b in result]
        return "\n".join(parts)
    return json.dumps(result, default=str)


class MCPHub:
    def __init__(self):
        settings.workspace.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "WORKSPACE_ROOT": str(settings.workspace),
            "DATABASE_URL": database_url(),
            "PYTHONIOENCODING": "utf-8",
        }
        self.client = MultiServerMCPClient({
            name: {
                "command": sys.executable,
                "args": [str(ROOT / "mcp_servers" / f"{name}_server.py")],
                "transport": "stdio",
                "env": env,
            }
            for name in SERVERS
        })
        self.loop = asyncio.new_event_loop()
        self.tools = {}
        self._ready = threading.Event()
        threading.Thread(target=self._run, daemon=True, name="mcp-hub").start()
        if not self._ready.wait(timeout=90):
            raise RuntimeError("MCP servers did not start")

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._open())
        self._ready.set()
        self.loop.run_forever()

    async def _open(self):
        self.stack = AsyncExitStack()
        for name in SERVERS:
            session = await self.stack.enter_async_context(self.client.session(name))
            for tool in await load_mcp_tools(session):
                self.tools[tool.name] = tool

    def call(self, name: str, args: dict, timeout: float = 60) -> str:
        with tracer.start_as_current_span(f"mcp.{name}") as span:
            span.set_attribute("tool.args", json.dumps(args)[:500])
            fut = asyncio.run_coroutine_threadsafe(self.tools[name].ainvoke(args), self.loop)
            try:
                out = _text(fut.result(timeout=timeout))
            except Exception as e:
                span.set_attribute("error", str(e)[:300])
                out = f"ERROR: {e}"
            span.set_attribute("tool.result_chars", len(out))
            return out


@lru_cache(maxsize=1)
def hub() -> MCPHub:
    return MCPHub()
