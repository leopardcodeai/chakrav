#!/usr/bin/env python3
"""Feeds camera frames and instrument marks into the ChakraV simulator.

What: takes pictures from the Mac's built-in camera (ffmpeg avfoundation, "MacBook Pro Camera"),
      scales and crops each to the view's exact size (368 x 276, chakra_core.h CHAKRA_CAM_W/H),
      writes it as a JPEG to one temp file that every frame overwrites, and tells the app on its
      line port (127.0.0.1:8711, CHAKRA_AI_PORT):
        source<TAB><text><TAB><camera|video|demo> once: the Camera page's source line, the mode mark
        frame<TAB><path><TAB><luma>               per frame; the app reads the file at once, the mean
                                                  luma (0..255) drives the camera light's Auto
        boxes<TAB>clear, then box<TAB><label><TAB><x><TAB><y><TAB><w><TAB><h><TAB><conf>
                                                  per frame with marks, normalised 0..1
      It follows the app's Camera settings, which come back on the same socket as
        camera<TAB><on 0|1><TAB><boxes 0|1><TAB><fps 1|2|4><TAB><cloud 0|1>
      and heard<TAB><chakra 0..6|-1>, which --detect passes on to the tracker (bowl_tracker.py).
      With the camera off it stops ffmpeg, so the Mac's camera (and its green light) is off too.
      Cloud AI (EXPERIMENTAL, off by default): only when it is On in the app AND an OPENAI_API_KEY or
      GEMINI_API_KEY is in the environment, each frame goes to tools/cloud_vision.py, a stub that
      sends nothing in v0. The source line adds "cloud stub" when a key is there.
        --demo        a drawn scene instead of the camera (a singing bowl, a tuning fork and
                      chimes on a floor, moving gently): for screenshots and the launcher's demo
        --video FILE  a video file instead of the camera, looped in real time, for tests without a
                      camera (its sound goes to the app through chakra_feed.py wav FILE --loop)
        --detect      real marks: each frame goes to tools/detect_owl.py (OWL-ViT, zero-shot, on the Mac)
        --demo-boxes  the stub detector: with --demo the drawn instruments' true boxes, over the
                      real camera plausible moving boxes that mark nothing real.
      Without --demo-boxes no boxes are sent: there is no detector yet, and the seen pill says so.
      Real detection is the next step (README, "Next"): an open-vocabulary detector such as
      OWL-ViT on the Mac first, later a trained ESPDet-Pico on the ESP32-S31.
Why:  owner 25.10.2026: "eine neue App, wo man auch das Kamerabild in einem Live-Mode sieht und wie
      er die Instrumente markiert und was er erkennt".
Privacy: the camera sees the owner's room. Frames exist only in one temp file in a private folder
      (0700), overwritten by each next frame and deleted at the end; nothing else is written,
      nothing is uploaded. Screenshots for the repo use --demo.
Pitfalls:
  * macOS asks once for the camera permission of the app that runs this (Terminal, Claude, the
    launcher's parent). Denied, ffmpeg fails at once: this script says so and waits; it never
    tries another way. Allow it in System Settings, Privacy & Security, Camera.
  * The camera runs at 30 fps natively; ffmpeg's fps filter picks the 1, 2 or 4 frames a second.
  * The app takes only frames of exactly 368 x 276 (images play at their native size in GSP).
Usage:  camera_live.py [--demo] [--demo-boxes] [--port 8711] [--device "MacBook Pro Camera"] [--wait]
        camera_live.py --demo --demo-boxes       the screenshots' source (tools/screens.py)
        camera_live.py --dry-run     says what it would open and send, opens nothing
"""
import argparse
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

W, H = 368, 276  # chakra_core.h CHAKRA_CAM_W, CHAKRA_CAM_H
DEFAULT_DEVICE = "MacBook Pro Camera"


class App:
    """The line socket to the simulator and the settings it sends back."""

    def __init__(self, port: int, wait: bool):
        self.on, self.boxes, self.fps, self.cloud = True, True, 2, False
        self.heard = -1  # the chakra the app hears now (its "heard" line), a hint for the tracker
        self.changed = threading.Event()
        self.closed = False
        for attempt in range(120 if wait else 1):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if attempt == (119 if wait else 0):
                    sys.exit(f"no ChakraV simulator on 127.0.0.1:{port} (./sim.sh first)")
                time.sleep(1)
        self.sock.settimeout(None)
        threading.Thread(target=self.read, daemon=True).start()

    def read(self) -> None:
        buf = b""
        while True:
            try:
                chunk = self.sock.recv(1024)
            except OSError:
                chunk = b""
            if not chunk:
                self.closed = True
                self.changed.set()
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                f = line.decode(errors="replace").split("\t")
                if len(f) == 2 and f[0] == "heard":
                    self.heard = int(f[1]) if f[1].lstrip("-").isdigit() else -1
                if len(f) == 3 and f[0] == "camlight":
                    # The Mac's camera has no light to switch; on the board this is the flash LED.
                    print(f"camera light {'on' if f[1] == '1' else 'off'}"
                          f"{' (the picture is dark)' if f[2] == '1' else ''}", flush=True)
                if len(f) >= 4 and f[0] == "camera":
                    on, boxes, fps = f[1] == "1", f[2] == "1", int(f[3]) if f[3] in ("1", "2", "4") else 2
                    cloud = len(f) >= 5 and f[4] == "1"
                    if (on, boxes, fps, cloud) != (self.on, self.boxes, self.fps, self.cloud):
                        self.on, self.boxes, self.fps, self.cloud = on, boxes, fps, cloud
                        print(f"settings: camera {'on' if on else 'off'}, boxes {'on' if boxes else 'off'}, "
                              f"{fps} fps, cloud AI {'on' if cloud else 'off'}", flush=True)
                        self.changed.set()

    def send(self, text: str) -> None:
        try:
            self.sock.sendall(text.encode())
        except OSError:
            self.closed = True
            self.changed.set()


class FrameFile:
    """The one temp file every frame overwrites (atomically, so the app never reads half a frame)."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="chakrav-camera-"))  # 0700
        self.path = self.dir / "frame.jpg"
        self.tmp = self.dir / "frame.part"

    def write(self, jpeg: bytes) -> str:
        self.tmp.write_bytes(jpeg)
        os.replace(self.tmp, self.path)
        return str(self.path)

    def remove(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


# ------------------------------------------------------------------ the demo scene and stub boxes --

def demo_objects(t: float) -> list[tuple[str, float, float, float, float, float]]:
    """Where the drawn instruments are at time t: (label, x, y, w, h, conf), normalised."""
    bx = 0.07 + 0.04 * math.sin(t * 0.5)
    objs = [("Singing bowl", bx, 0.40, 0.38, 0.44, 0.90 + 0.05 * math.sin(t * 1.3))]
    objs.append(("Tuning fork", 0.52, 0.24 + 0.03 * math.sin(t * 0.8), 0.12, 0.54, 0.78 + 0.08 * math.sin(t * 0.9)))
    if math.sin(t * 0.25) > -0.3:  # the chimes leave the picture now and then
        objs.append(("Chimes", 0.84, 0.06, 0.14, 0.44, 0.71 + 0.06 * math.sin(t * 1.7)))
    return objs


def demo_frame(t: float) -> bytes:
    """A drawn room: a warm wall, a wooden floor, the instruments of demo_objects(t)."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFilter
    s = 2  # drawn at twice the size, then scaled down: smooth edges
    im = Image.new("RGB", (W * s, H * s), (44, 36, 48))
    d = ImageDraw.Draw(im)
    for y in range(int(H * 0.62) * s):  # wall, lit from the top left
        k = y / (H * 0.62 * s)
        d.line([(0, y), (W * s, y)], fill=(int(70 - 30 * k), int(58 - 26 * k), int(72 - 28 * k)))
    floor = int(H * 0.62) * s
    d.rectangle([0, floor, W * s, H * s], fill=(92, 64, 44))
    for i in range(0, W * s, 46 * s // 2):
        d.line([(i, floor), (i - 60, H * s)], fill=(80, 55, 38), width=2)
    for label, x, y, w, h, _ in demo_objects(t):
        X, Y, Wd, Ht = x * W * s, y * H * s, w * W * s, h * H * s
        if label == "Singing bowl":
            d.ellipse([X + Wd * 0.05, Y + Ht * 0.80, X + Wd * 0.95, Y + Ht * 1.0], fill=(40, 28, 20))  # shadow
            d.chord([X, Y + Ht * 0.05, X + Wd, Y + Ht * 0.95], 0, 180, fill=(196, 150, 60))
            d.ellipse([X, Y + Ht * 0.36, X + Wd, Y + Ht * 0.64], fill=(226, 184, 92))
            d.ellipse([X + Wd * 0.06, Y + Ht * 0.39, X + Wd * 0.94, Y + Ht * 0.61], fill=(120, 86, 38))
            d.arc([X + Wd * 0.1, Y + Ht * 0.30, X + Wd * 0.9, Y + Ht * 0.88], 25, 155, fill=(240, 205, 120), width=3 * s)
        elif label == "Tuning fork":
            cx = X + Wd / 2
            d.rectangle([cx - 3 * s, Y + Ht * 0.55, cx + 3 * s, Y + Ht], fill=(205, 210, 220))
            d.rounded_rectangle([cx - Wd * 0.32, Y + Ht * 0.45, cx + Wd * 0.32, Y + Ht * 0.60], radius=8 * s,
                                fill=(205, 210, 220))
            for side in (-1, 1):
                ex = cx + side * Wd * 0.26
                d.rectangle([ex - 4 * s, Y, ex + 4 * s, Y + Ht * 0.55], fill=(220, 225, 235))
        else:
            d.line([(X, Y + 4 * s), (X + Wd, Y + 4 * s)], fill=(120, 90, 60), width=4 * s)
            for k in range(5):
                tx = X + Wd * (0.1 + 0.2 * k)
                top = Y + Ht * (0.10 + 0.05 * (k % 3))
                d.line([(tx, Y + 4 * s), (tx, top)], fill=(150, 150, 160), width=1 * s)
                d.rectangle([tx - 3 * s, top, tx + 3 * s, top + Ht * (0.80 - 0.09 * k)], fill=(200, 200, 210))
    im = im.filter(ImageFilter.GaussianBlur(0.6)).resize((W, H), Image.LANCZOS)
    out = BytesIO()
    im.save(out, "JPEG", quality=82)
    return out.getvalue()


class StubBoxes:
    """--demo-boxes over the real camera: two or three boxes that drift like a detector's would.
    They mark nothing real; the real detector comes next (README)."""

    def __init__(self):
        self.rng = random.Random(7)
        self.t0 = time.monotonic()

    def boxes(self):
        t = time.monotonic() - self.t0
        # The first box counts as played for 2 s out of every 5, so both looks can be checked.
        played = (t % 5.0) < 2.0
        return [(label, min(0.95 - w, max(0.0, x + self.rng.uniform(-0.01, 0.01))), y, w, h,
                 max(0.3, min(0.99, c + self.rng.uniform(-0.03, 0.03))), 1 if (k == 0 and played) else 0)
                for k, (label, x, y, w, h, c) in enumerate(demo_objects(t))]


# ------------------------------------------------------------------ the camera --

def ffmpeg_camera(device: str, fps: int, video: str | None = None, scale: int = 1) -> subprocess.Popen:
    """Frames of the view's crop; scale 2 gives the detector twice the size (app_frame() makes the app's)."""
    w, h = W * scale, H * scale
    vf = f"fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
    # A video file instead of the camera: in real time, looped, its sound left to chakra_feed.py.
    src = ["-re", "-stream_loop", "-1", "-i", video, "-an"] if video else \
        ["-f", "avfoundation", "-framerate", "30", "-i", f"{device}:none"]
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", *src, "-vf", vf, "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def app_frame(jpeg: bytes) -> bytes:
    """The view's exact W x H from a bigger frame of the same crop."""
    from io import BytesIO
    from PIL import Image
    out = BytesIO()
    Image.open(BytesIO(jpeg)).convert("RGB").resize((W, H), Image.LANCZOS).save(out, "JPEG", quality=85)
    return out.getvalue()


def jpeg_frames(proc: subprocess.Popen):
    """Whole JPEGs from ffmpeg's mjpeg pipe (FFD8 ... FFD9; 0xFF is stuffed inside the data)."""
    buf = b""
    while True:
        chunk = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(65536)
        if not chunk:
            return
        buf += chunk
        while True:
            start = buf.find(b"\xff\xd8")
            end = buf.find(b"\xff\xd9", start + 2) if start >= 0 else -1
            if start < 0 or end < 0:
                break
            yield buf[start:end + 2]
            buf = buf[end + 2:]


def frame_stats(jpeg: bytes) -> tuple[int, int]:
    """Mean luma and contrast (the luma's standard deviation), 0..255, of a JPEG; (-1, -1) without
    Pillow. Shared with tools/check_frames.py."""
    try:
        from io import BytesIO

        from PIL import Image, ImageStat
    except ImportError:
        return -1, -1
    with Image.open(BytesIO(jpeg)) as im:
        st = ImageStat.Stat(im.convert("L"))
    return int(st.mean[0] + 0.5), int(st.stddev[0] + 0.5)


class Detector:
    """tools/detect_owl.py in the AI venv: a frame in, its instrument boxes out (OWL-ViT, zero-shot)."""
    VENV = os.path.expanduser("~/Library/Application Support/LeopardCode/chakra/ai_venv_eat/bin/python")

    def __init__(self):
        here = os.path.dirname(os.path.abspath(__file__))
        self.proc = subprocess.Popen([self.VENV, os.path.join(here, "detect_owl.py")], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def boxes(self, jpeg: bytes, heard: int = -1):
        import json
        import struct
        try:
            self.proc.stdin.write(struct.pack(">Ib", len(jpeg), max(-1, min(6, heard))) + jpeg)
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            return [tuple(b) for b in json.loads(line)] if line else None
        except (OSError, ValueError):
            return None


def cloud_key() -> bool:
    return any(os.environ.get(k, "").strip() for k in ("OPENAI_API_KEY", "GEMINI_API_KEY"))


def send_frame(app: App, files: FrameFile, jpeg: bytes, boxes) -> None:
    if app.cloud and cloud_key():  # EXPERIMENTAL: both switched on and a key; v0 sends nothing out
        import cloud_vision
        boxes = cloud_vision.ask(jpeg) or boxes
    lines = f"frame\t{files.write(jpeg)}\t{frame_stats(jpeg)[0]}\n"
    if app.boxes and boxes is not None:
        lines += "boxes\tclear\n" + "".join(
            f"box\t{b[0]}\t{b[1]:.3f}\t{b[2]:.3f}\t{b[3]:.3f}\t{b[4]:.3f}\t{b[5]:.2f}"
            + (f"\t{int(b[6])}" if len(b) > 6 else "") + "\n" for b in boxes[:4])
    app.send(lines)


def run_camera(app: App, files: FrameFile, device: str, stub: StubBoxes | None, video: str | None = None) -> None:
    told = False
    while not app.closed:
        if not app.on:
            app.changed.wait(1.0)
            app.changed.clear()
            continue
        app.changed.clear()
        fps = app.fps
        # OWL-ViT finds the bowls at 0.05 in the view's 368 x 276 and at 0.2 to 0.4 in twice that
        # (25.10.2026, the owner's video): the detector gets the double size, the app its own.
        big = isinstance(stub, Detector)
        proc = ffmpeg_camera(device, fps, video, 2 if big else 1)
        print(f"{'video ' + os.path.basename(video) if video else 'camera open: ' + device}, {fps} fps", flush=True)
        n = 0
        for jpeg in jpeg_frames(proc):
            n += 1
            boxes = stub.boxes(jpeg, app.heard) if big else stub.boxes() if stub else None
            send_frame(app, files, app_frame(jpeg) if big else jpeg, boxes)
            if app.closed or not app.on or app.fps != fps:
                break
        proc.terminate()
        try:
            _, err = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
        if n == 0 and not app.closed:
            text = (err or b"").decode(errors="replace").strip().splitlines()
            if not told:
                print("the camera gave no picture: " + (text[-1] if text else "ffmpeg ended") + "\n"
                      "  if macOS refused it: System Settings, Privacy & Security, Camera, allow the app that "
                      "started this (Terminal or Claude); this script does not work around it", flush=True)
                told = True
            app.changed.wait(10)  # try again later, or after a settings change
        elif not app.on:
            print("camera off (the settings), ffmpeg stopped", flush=True)


def run_demo(app: App, files: FrameFile, boxes: bool) -> None:
    t0 = time.monotonic()
    while not app.closed:
        if not app.on:
            app.changed.wait(1.0)
            app.changed.clear()
            continue
        t = time.monotonic() - t0
        send_frame(app, files, demo_frame(t), demo_objects(t) if boxes else None)
        app.changed.wait(1.0 / app.fps)
        app.changed.clear()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=int(os.environ.get("CHAKRA_AI_PORT", "8711")))
    ap.add_argument("--device", default=DEFAULT_DEVICE, help="the avfoundation camera by name (ffmpeg -f avfoundation "
                    "-list_devices true -i '')")
    ap.add_argument("--demo", action="store_true", help="a drawn scene instead of the camera")
    ap.add_argument("--video", metavar="FILE", help="a video file instead of the camera, looped in real time")
    ap.add_argument("--detect", action="store_true",
                    help="real instrument marks with OWL-ViT on the Mac (tools/detect_owl.py, the AI venv)")
    ap.add_argument("--demo-boxes", action="store_true",
                    help="stub boxes (no detector yet): the drawn scene's true ones, or drifting ones over the camera")
    ap.add_argument("--wait", action="store_true", help="retry for 2 min until the simulator listens")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, open nothing")
    a = ap.parse_args()
    source = "Demo scene" if a.demo else f"Video {os.path.basename(a.video)[:18]}" if a.video else "Mac camera"
    if a.video and not os.path.exists(a.video):
        sys.exit(f"no such video: {a.video}")
    if a.dry_run:
        what = ("a drawn demo scene" if a.demo else f"ffmpeg avfoundation '{a.device}' scaled to {W}x{H}") + \
            (" with stub boxes" if a.demo_boxes else ", no boxes")
        print(f"would connect to 127.0.0.1:{a.port}, send 'source {source} · {W} × {H}', then {what}, "
              f"one JPEG in a private temp folder, overwritten per frame")
        return
    if not a.demo and not shutil.which("ffmpeg"):
        sys.exit("ffmpeg missing: brew install ffmpeg")
    app = App(a.port, a.wait)
    kind = "demo" if a.demo else "video" if a.video else "camera"
    size = "" if a.video else f" · {W} × {H}"  # a video's name is long enough for the line
    app.send(f"source\t{source}{size}" + (" · cloud stub" if cloud_key() else "") + f"\t{kind}\n")
    files = FrameFile()
    print(f"{source} to 127.0.0.1:{a.port}; Ctrl-C stops", flush=True)
    try:
        if a.demo:
            run_demo(app, files, a.demo_boxes)
        else:
            marks = Detector() if a.detect and os.path.exists(Detector.VENV) else StubBoxes() if a.demo_boxes else None
            if a.detect and not isinstance(marks, Detector):
                print("no AI venv: --detect needs ~/Library/Application Support/LeopardCode/chakra/ai_venv_eat", flush=True)
            run_camera(app, files, a.device, marks, a.video)
    except KeyboardInterrupt:
        pass
    finally:
        files.remove()


if __name__ == "__main__":
    main()
