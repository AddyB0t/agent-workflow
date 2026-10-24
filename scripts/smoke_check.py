"""Check that the external pieces work: E2B sandbox, embedded Postgres, Playwright."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.config import settings  # noqa: E402


def main():
    from e2b_code_interpreter import Sandbox

    with Sandbox.create(api_key=settings.e2b_api_key, timeout=120) as sbx:
        r = sbx.commands.run("python --version && python -c 'import pytest; print(pytest.__version__)'")
        print("e2b:", r.stdout.strip().replace("\n", " | "))

    from agent.db import connect

    with connect() as conn:
        print("postgres:", conn.execute("select version() as v").fetchone()["v"][:40])

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto("https://example.com")
        print("playwright:", page.title())
        b.close()


if __name__ == "__main__":
    main()
