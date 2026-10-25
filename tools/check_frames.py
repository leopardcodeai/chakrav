#!/usr/bin/env python3
"""Measures what the camera view gets: brightness, contrast, how much the picture changes, and
when the camera light's Auto would switch on.

What: runs the frames of a video (or the drawn demo scene) at the app's frame rate and size
      (368 x 276, as tools/camera_live.py sends them) through
        luma      the mean luma 0..255 (what the app's Auto reads)
        contrast  the luma's standard deviation: low means flat, hard to detect anything in
        change    the mean luma difference to the frame before: a moving or changing background
        boxes     how many marks the stub detector gives (no real detector yet)
        light     the camera light's Auto, with the same thresholds and hysteresis as
                  chakra_core.c (LUMA_DARK and the lines after it)
      and prints one row per second plus a summary.
Why:  owner 25.10.2026: "wie das bei Video dann immer in der Kamera den Hintergrund ändert, und es
      ist eher dunkel, wenn keine Musik, dann erkennt der vielleicht schlechter; das müssen wir
      alles checken". This is the measurement; the real detector (OWL-ViT) comes later.
Privacy: reads the video, writes nothing. Test videos stay local and are never committed.
Pitfalls:
  * A video cannot answer the light: the light brightens nothing in a recording, so after Auto
    switched on, its "room got brighter" test only fires if the video itself gets brighter.
  * The stub's boxes mark nothing real over a video; the count only shows the pipeline runs.
Usage:  check_frames.py --video FILE [--fps 2] [--seconds 60]
        check_frames.py --demo [--seconds 20]
        check_frames.py --video FILE --dry-run
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import camera_live as cam  # noqa: E402

# chakra_core.c, "camera light": keep these equal.
LUMA_DARK, LUMA_BRIGHTER = 50, 30
LIGHT_SWITCH_MS, LIGHT_MIN_ON_MS, LIGHT_BASE_MS = 2000, 10000, 1000
FLAT = 20  # a contrast below this: a flat picture (an estimate, to be checked with the real detector)


class AutoLight:
    """chakra_core.c auto_light(), step for step."""

    def __init__(self):
        self.lit, self.dark, self.dark_since, self.bright_since, self.lit_at, self.base = False, False, 0, 0, 0, -1
        self.switches = 0

    def step(self, t: int, luma: int) -> bool:
        t = t or 1
        if not self.lit:
            self.dark = luma < LUMA_DARK
            self.bright_since = 0
            if not self.dark:
                self.dark_since = 0
            elif not self.dark_since:
                self.dark_since = t
            elif t - self.dark_since >= LIGHT_SWITCH_MS:
                self.lit, self.lit_at, self.base = True, t, -1
                self.switches += 1
            return self.lit
        if self.base < 0 and t - self.lit_at >= LIGHT_BASE_MS:
            self.base = luma
        brighter = self.base >= 0 and luma > self.base + LUMA_BRIGHTER and luma >= LUMA_DARK
        if not brighter or t - self.lit_at < LIGHT_MIN_ON_MS:
            self.bright_since = 0
        elif not self.bright_since:
            self.bright_since = t
        elif t - self.bright_since >= LIGHT_SWITCH_MS:
            self.lit, self.dark, self.dark_since = False, False, 0
            self.switches += 1
        return self.lit


def video_frames(path: str, fps: int, seconds: float):
    vf = f"fps={fps},scale={cam.W}:{cam.H}:force_original_aspect_ratio=increase,crop={cam.W}:{cam.H}"
    proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", path, "-t", str(seconds), "-an", "-vf", vf,
                             "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], stdout=subprocess.PIPE)
    yield from cam.jpeg_frames(proc)
    proc.wait()


def gray(jpeg: bytes):
    from io import BytesIO

    from PIL import Image
    with Image.open(BytesIO(jpeg)) as im:
        return im.convert("L").copy()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--video", metavar="FILE")
    src.add_argument("--demo", action="store_true")
    ap.add_argument("--fps", type=int, default=2, choices=[1, 2, 4])
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.video and not os.path.exists(a.video):
        sys.exit(f"no such video: {a.video}")
    if a.dry_run:
        print(f"would read {a.video or 'the demo scene'} at {a.fps} fps for up to {a.seconds:.0f} s, "
              f"{cam.W} x {cam.H}, and print luma, contrast, change, stub boxes and the light's Auto per second")
        return
    from PIL import ImageChops, ImageStat
    if a.demo:
        frames = (cam.demo_frame(i / a.fps) for i in range(int(a.seconds * a.fps)))
    else:
        frames = video_frames(a.video, a.fps, a.seconds)
    stub, light, prev = cam.StubBoxes(), AutoLight(), None
    rows, sec = [], []
    print(f"{'s':>4} {'luma':>5} {'contr':>5} {'change':>6} {'boxes':>5}  light")
    for i, jpeg in enumerate(frames):
        t = i * 1000 // a.fps
        luma, contrast = cam.frame_stats(jpeg)
        g = gray(jpeg)
        change = ImageStat.Stat(ImageChops.difference(g, prev)).mean[0] if prev else 0.0
        prev = g
        boxes = cam.demo_objects(t / 1000) if a.demo else stub.boxes()
        lit = light.step(t, luma)
        sec.append((luma, contrast, change, len(boxes), lit, light.dark))
        if len(sec) == a.fps:
            m = [sum(x[k] for x in sec) / len(sec) for k in range(4)]
            on, dark = sec[-1][4], any(x[5] for x in sec)
            rows.append((m[0], m[1], m[2], on, dark, m[1] < FLAT))
            note = ("on" if on else "off") + (" · dark" if dark else "") + (" · flat" if m[1] < FLAT else "")
            print(f"{len(rows):>4} {m[0]:>5.0f} {m[1]:>5.0f} {m[2]:>6.1f} {m[3]:>5.0f}  {note}", flush=True)
            sec = []
    if not rows:
        sys.exit("no frames")
    n = len(rows)
    share = lambda k: 100 * sum(1 for r in rows if r[k]) // n  # noqa: E731
    print(f"\n{n} s: mean luma {sum(r[0] for r in rows) / n:.0f}, contrast {sum(r[1] for r in rows) / n:.0f}, "
          f"change {sum(r[2] for r in rows) / n:.1f} (max {max(r[2] for r in rows):.1f}); "
          f"dark {share(4)} %, flat {share(5)} %, light on {share(3)} % with {light.switches} switch(es)")


if __name__ == "__main__":
    main()
