"""MCP server: file access confined to the agent workspace directory."""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(os.environ["WORKSPACE_ROOT"]).resolve()
mcp = FastMCP("files", log_level="WARNING")


def _safe(path: str) -> Path:
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError("Path escapes the workspace")
    return p


@mcp.tool()
def list_files(path: str = ".") -> list[str]:
    """List files (recursively) under a workspace directory."""
    base = _safe(path)
    return sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in base.rglob("*") if p.is_file())


@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file from the workspace."""
    return _safe(path).read_text(encoding="utf-8")


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write a text file in the workspace. The workflow only calls this after human approval."""
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {len(content)} chars to {path}"


if __name__ == "__main__":
    mcp.run()
