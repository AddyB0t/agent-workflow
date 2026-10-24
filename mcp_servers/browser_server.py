"""MCP server: read a web page with a headless Chromium (Playwright)."""

from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

BLOCKED = ("github.com", "githubusercontent.com", "gitlab.com", "jkoppel.github.io")
mcp = FastMCP("browser", log_level="WARNING")


@mcp.tool()
async def fetch_page(url: str, max_chars: int = 4000) -> str:
    """Open a URL in a headless browser and return the visible text of the page."""
    host = urlparse(url).hostname or ""
    if urlparse(url).scheme not in ("http", "https") or any(host.endswith(b) for b in BLOCKED):
        return "Blocked: this domain is not allowed (it may contain benchmark solutions)."
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.goto(url, timeout=20000, wait_until="domcontentloaded")
            text = await page.inner_text("body")
        finally:
            await browser.close()
    if "quixbugs" in text.lower():
        return "Blocked: page mentions the benchmark."
    return text[: min(max_chars, 8000)]


if __name__ == "__main__":
    mcp.run()
