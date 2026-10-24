"""Screen-record the web UI: start a run, watch the steps, approve, see it pass.

Needs the UI running: uv run uvicorn ui.app:app --port 8100
Usage: python scripts/record_demo.py <task> <out.webm>
"""

import shutil
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

task, out = sys.argv[1], Path(sys.argv[2])
tmp = out.parent / "_video"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 800}, record_video_dir=str(tmp),
                        record_video_size={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8100/")
    page.wait_for_timeout(2000)
    page.select_option("#task", task)
    page.wait_for_timeout(1000)
    page.click("text=Start run")
    deadline = time.time() + 240
    while time.time() < deadline and not page.locator("button.ok").count():
        page.wait_for_timeout(2000)
        page.mouse.wheel(0, 300)
    page.locator(".approval").scroll_into_view_if_needed()
    page.wait_for_timeout(5000)
    page.click("button.ok")
    while time.time() < deadline and "passed" not in page.inner_text("#detail h3"):
        page.wait_for_timeout(2000)
    page.mouse.wheel(0, -5000)
    page.wait_for_timeout(4000)
    for _ in range(6):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(1200)
    video = page.video.path()
    ctx.close()
    b.close()
shutil.move(video, out)
shutil.rmtree(tmp, ignore_errors=True)
print(f"wrote {out}")
