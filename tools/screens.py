#!/usr/bin/env python3
"""Takes ChakraV's standard screenshots in the simulator, with demo sources only.

What: (re)generates the scene (optionally with another frame width), starts sim.sh, feeds it a
      steady demo tone (tools/chakra_feed.py tone) and the drawn demo scene with its boxes
      (tools/camera_live.py --demo --demo-boxes), and saves through tools/sim_shot.py, pixel for pixel:
        main.png         the main screen: frame, camera view with boxes, name, pills, spectrum
        settings.png     the gear's first page
        camera.png       the Camera page (camera, boxes, frame rate, source)
        connections.png  the lamps
      then stops everything it started. Never the real camera: frames of the owner's room must
      not land in a file.
Why:  every changed screen is looked at in the simulator before it is called done (DESIGN.md);
      the owner asked for design variants to compare (25.10.2026).
Pitfalls:
  * Uses the ports 8710 and 8711: not while the launcher runs ChakraV. The preview's port is read
    from sim.sh's "Preview:" line (3222 may belong to another app's simulator).
  * A first build of the backend takes up to a minute; the steps wait for "Preview:".
  * --frame changes main.json; the script writes the default back at the end.
Usage:  tools/screens.py OUTDIR [--frame 20] [--hz 174.6]
        tools/screens.py OUTDIR --dry-run
"""
import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SCENE = HERE / "components/app_chakra/ui/make_scene.py"
UV = "uv"


def tree(pid: int) -> list[int]:
    out = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True).stdout
    kids: dict[int, list[int]] = {}
    for row in out.split("\n"):
        p = row.split()
        if len(p) == 2:
            kids.setdefault(int(p[1]), []).append(int(p[0]))
    found, todo = [], [pid]
    while todo:
        for k in kids.get(todo.pop(), []):
            found.append(k)
            todo.append(k)
    return found


def stop(proc: subprocess.Popen) -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        for pid in [proc.pid, *tree(proc.pid)]:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        try:
            proc.wait(timeout=6)
            return
        except subprocess.TimeoutExpired:
            pass
    proc.kill()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", type=Path)
    ap.add_argument("--frame", type=int, default=28, help="the coloured frame's width (make_scene.py FRAME)")
    ap.add_argument("--hz", type=float, default=174.6, help="the demo tone (174.6 Hz: F3, Heart)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    f = a.frame
    tw = (480 - 2 * f - 8 - 12) // 3
    tab = lambda j: f + 4 + j * (tw + 6) + tw // 2  # noqa: E731
    gear = (480 - f - 30, f + 26)
    tabs_y = f + 52 + 4 + 17
    steps = ["wait 10", "shot main", f"tap {gear[0]} {gear[1]}", "wait 1.5", "shot settings",
             f"tap {tab(2)} {tabs_y}", "wait 1.5", "shot camera", f"tap {tab(1)} {tabs_y}", "wait 1.5",
             "shot connections", f"tap {tab(0)} {tabs_y}", f"tap {gear[0]} {gear[1]}"]
    if a.dry_run:
        print(f"would write the scene with FRAME={f}, start sim.sh, chakra_feed.py tone {a.hz}, "
              f"camera_live.py --demo --demo-boxes, then sim_shot.py {steps} into {a.out}")
        return
    # No API key reaches the children: the shots show the app as anyone sees it, Cloud AI without a key.
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    env = {**env, "CHAKRAV_FRAME": str(f), "BROWSER": "true", "CHAKRA_SIM_SECONDS": "120",
           "CHAKRA_FEED_PORT": "8710", "CHAKRA_AI_PORT": "8711"}
    subprocess.run([sys.executable, str(SCENE)], env=env, check=True)
    a.out.mkdir(parents=True, exist_ok=True)
    log = open(a.out / "sim.log", "w")
    sim = subprocess.Popen(["sh", str(HERE / "sim.sh")], cwd=HERE, env=env, stdout=log, stderr=subprocess.STDOUT)
    feeds = []
    try:
        # The preview takes 3222 or the next free port (another app's simulator may hold 3222): the
        # shots go to the address this simulator printed, never to a fixed one.
        url, deadline = None, time.time() + 240
        while time.time() < deadline and not url:
            m = re.search(r"^Preview: (http://127\.0\.0\.1:\d+/)", (a.out / "sim.log").read_text(errors="replace"), re.M)
            url = m.group(1) if m else None
            time.sleep(0.5)
        if not url:
            sys.exit("the simulator printed no preview address, see sim.log")
        feeds.append(subprocess.Popen([sys.executable, str(HERE / "tools/chakra_feed.py"), "tone", str(a.hz),
                                       "--seconds", "40", "--wait", "--port", "8710"], env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        feeds.append(subprocess.Popen([sys.executable, str(HERE / "tools/camera_live.py"), "--demo", "--demo-boxes", "--wait"],
                                      env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        subprocess.run([UV, "run", "-q", "--python", "3.14", "--with", "websockets", "python",
                        str(HERE / "tools/sim_shot.py"), "--url", url, "--out", str(a.out), *steps], check=True)
    finally:
        for p in feeds:
            p.terminate()
        stop(sim)
        log.close()
        if f != 28:
            env.pop("CHAKRAV_FRAME")
            subprocess.run([sys.executable, str(SCENE)], env=env, check=True)  # the default back


if __name__ == "__main__":
    main()
