#!/usr/bin/env python3
"""Screenshots of the running simulator's preview, pixel for pixel, through headless Chrome.

What: opens the simulator's browser preview (--url; take it from sim.sh's "Preview:" line, as
      another app's simulator may hold the default 3222) in headless Google
      Chrome, runs a list of steps on its canvas and saves each "shot" as the canvas's own
      480 x 480 PNG (canvas.toDataURL, so no browser scaling blurs the check for sharpness).
      Steps: "wait S", "tap X Y" (a touch at screen pixels), "hold X Y S", "shot NAME".
Why:  every screen change is looked at before it is called done (DESIGN.md); the scene-only
      --frame of sim.sh shows no runtime state (camera frames, boxes, settings pages).
Privacy: use it only while camera_live.py runs with --demo: a shot of the live camera would put
      the owner's room into a file.
Pitfalls:
  * Needs the websockets package: run it through uv (see Usage).
  * The preview throttles in a background tab; headless Chrome is never one.
  * setPointerCapture() throws for synthetic pointers; it is wrapped in try/catch first.
Usage:  uv run -q --python 3.14 --with websockets python tools/sim_shot.py --out DIR \\
            "wait 3" "shot main" "tap 432 50" "wait 1" "shot settings"
        sim_shot.py --dry-run ...   prints the steps, opens nothing
"""
import argparse
import asyncio
import base64
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

JS_TOUCH = """
(type, x, y) => {
  const c = document.querySelector('canvas'); const r = c.getBoundingClientRect();
  c.dispatchEvent(new PointerEvent(type, {bubbles: true, cancelable: true, pointerId: 7, isPrimary: true,
    pointerType: 'touch', clientX: r.left + x * r.width / 480, clientY: r.top + y * r.height / 480,
    buttons: type === 'pointerup' ? 0 : 1}));
  return true;
}
"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def run(url: str, steps: list[str], out: Path) -> list[str]:
    import websockets
    port = free_port()
    profile = tempfile.mkdtemp(prefix="chakrav-shot-")
    chrome = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                               "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
                               f"--remote-debugging-port={port}", f"--user-data-dir={profile}",
                               "--window-size=700,700", url],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    saved = []
    try:
        ws_url = None
        for _ in range(100):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as r:
                    pages = [p for p in json.loads(r.read()) if p.get("type") == "page"]
                if pages:
                    ws_url = pages[0]["webSocketDebuggerUrl"]
                    break
            except OSError:
                pass
            time.sleep(0.1)
        if not ws_url:
            sys.exit("headless Chrome did not answer")
        async with websockets.connect(ws_url, max_size=None) as ws:
            n = 0

            async def call(method, **params):
                nonlocal n
                n += 1
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                while True:
                    msg = json.loads(await ws.recv())
                    if msg.get("id") == n:
                        return msg.get("result", {})

            async def js(expr):
                r = await call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
                return r.get("result", {}).get("value")

            for _ in range(100):  # the canvas and the first frames
                if await js("!!document.querySelector('canvas')"):
                    break
                await asyncio.sleep(0.1)
            # The preview calls setPointerCapture(), which throws for synthetic pointers (as in the
            # launcher's INJECT): wrapped, so taps arrive.
            await js("(() => { const o = HTMLElement.prototype.setPointerCapture; "
                     "HTMLElement.prototype.setPointerCapture = function (id) { try { o.call(this, id) } catch (e) {} }; "
                     "return true })()")
            for step in steps:
                f = step.split()
                if f[0] == "wait":
                    await asyncio.sleep(float(f[1]))
                elif f[0] == "tap":
                    await js(f"({JS_TOUCH})('pointerdown', {f[1]}, {f[2]})")
                    await asyncio.sleep(0.08)
                    await js(f"({JS_TOUCH})('pointerup', {f[1]}, {f[2]})")
                elif f[0] == "hold":
                    await js(f"({JS_TOUCH})('pointerdown', {f[1]}, {f[2]})")
                    await asyncio.sleep(float(f[3]))
                    await js(f"({JS_TOUCH})('pointerup', {f[1]}, {f[2]})")
                elif f[0] == "shot":
                    data = await js("document.querySelector('canvas').toDataURL('image/png')")
                    path = out / f"{f[1]}.png"
                    path.write_bytes(base64.b64decode(data.split(",", 1)[1]))
                    saved.append(str(path))
                    print(path, flush=True)
                else:
                    sys.exit(f"unknown step: {step}")
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("steps", nargs="+")
    ap.add_argument("--url", default="http://127.0.0.1:3222/")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        print(f"would open {a.url} in headless Chrome and run: {'; '.join(a.steps)}; PNGs to {a.out}")
        return
    a.out.mkdir(parents=True, exist_ok=True)
    asyncio.run(run(a.url, a.steps, a.out))


if __name__ == "__main__":
    main()
