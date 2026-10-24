"""MCP server: web search through Tavily.

Results from QuixBugs itself are removed so the agent cannot copy the reference fixes.
"""

import os

from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

BLOCKED_DOMAINS = ["github.com", "githubusercontent.com", "gitlab.com", "jkoppel.github.io"]
mcp = FastMCP("search", log_level="WARNING")
client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web. Returns title, url and a content snippet for each result."""
    res = client.search(query=query, max_results=min(max_results, 8), exclude_domains=BLOCKED_DOMAINS)
    out = []
    for r in res.get("results", []):
        text = f"{r.get('title', '')} {r.get('url', '')} {r.get('content', '')}".lower()
        if "quixbugs" in text:
            continue
        out.append({"title": r.get("title"), "url": r.get("url"), "snippet": (r.get("content") or "")[:600]})
    return out


if __name__ == "__main__":
    mcp.run()
