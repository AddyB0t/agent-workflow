"""MCP server: read-only SQL over the run-history database, plus task memory lookup."""

import os

import psycopg
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row

DSN = os.environ["DATABASE_URL"]
mcp = FastMCP("db", log_level="WARNING")


def _query(sql: str, params=()) -> list[dict]:
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.read_only = True
        rows = conn.execute(sql, params).fetchmany(50)
    return [{k: (v if isinstance(v, (int, float, str, bool, type(None))) else str(v)) for k, v in r.items()} for r in rows]


@mcp.tool()
def query(sql: str) -> list[dict]:
    """Run a read-only SELECT on tables runs, steps, approvals, costs, memory (max 50 rows)."""
    if not sql.lstrip().lower().startswith(("select", "with")):
        raise ValueError("Only SELECT queries are allowed")
    return _query(sql)


@mcp.tool()
def recall_memory(task: str) -> list[dict]:
    """Notes saved from earlier runs of the same task (most recent first)."""
    return _query("select note, ts from memory where task = %s order by ts desc limit 5", (task,))


if __name__ == "__main__":
    mcp.run()
