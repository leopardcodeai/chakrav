#!/usr/bin/env python3
"""Feeds camera frames and instrument marks into the ChakraV simulator.

What: takes pictures from the Mac's built-in camera (ffmpeg avfoundation, "MacBook Pro Camera") or
      a video, emulates what the ESP-Mosaico's camera module gives the app (--module, below),
      writes each frame as a JPEG of the view's exact size (400 x 224, 16:9, chakra_core.h
      CHAKRA_CAM_W/H) to one temp file that every frame overwrites, and tells the app on its line
      port (127.0.0.1:8711, CHAKRA_AI_PORT):
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
        --module      v1.4 (default: the SC101IOT module the board is expected with) or v1.2
                      (OV3640). --mount landscape (default) keeps the module's frame upright as it comes,
                      1280 x 720; --mount portrait turns it, as when the module sits sideways:
                      V1.4 720 x 1280 (9:16), V1.2 768 x 1024 (3:4). The app shows the centre
                      16:9 band of it at the board's 1/16 scale step (view_crop, as main/camera.c):
                      landscape V1.4 its whole frame at 5/16 (73 x 42 degrees), V1.2 its centre
                      916 x 512 at 7/16 (about 51 x 30); portrait a 712 x 400 band at 9/16 (about
                      42 x 26 on V1.4). A --video becomes the upright frame (scaled to cover it,
                      centred), then that band. The Mac camera's 16:9 picture is cut to the band's
                      field of view, limited to what the Mac sees (its 70 degrees are an estimate, as
                      in apps/camera cam_twin.py): V1.4's 73 degrees are wider, so the Mac's whole
                      picture.
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
  * The app takes only frames of exactly 400 x 224 (images play at their native size in GSP).
  * The detector gets more pixels than the app: with a video the whole upright frame at 3/4 of its
    size (960 x 540 on V1.4, as before the 16:9 view), from the Mac camera the view at twice its size
    (800 x 448). OWL-ViT scores bowls far better there; the app's frame is cut and scaled from it.
    Boxes are normalised; to_view() moves the detector's into the view, the identity where the view
    is the whole frame (V1.4 landscape). Portrait mount: the view is a 16:9 band across the upright
    portrait frame, so to_view() shifts and stretches y and drops what lies outside.
  * Not emulated: the sensor's colour, exposure, noise and lens (manual focus), and its frame
    rate (the app asks for 1, 2 or 4 fps). apps/camera cam_twin.py models the module further.
Usage:  camera_live.py [--demo] [--demo-boxes] [--module v1.4|v1.2] [--video FILE] [--detect] [--port 8711]
                      [--device "MacBook Pro Camera"] [--wait]
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

W, H = 400, 224   # the 16:9 view: chakra_core.h CHAKRA_CAM_W/H, ui/make_scene.py CAM_W/H
DETECT_K = 0.75   # a video's upright frame goes to the detector at this share of its size (960 x 540 on V1.4)
DEFAULT_DEVICE = "MacBook Pro Camera"
# The ESP-Mosaico camera modules (Espressif user_guide_camera; apps/camera cam_twin.py MODULES).
# raw: the sensor frame as it comes (landscape). The module can be mounted either way (owner 26.10.2026:
# "Querformat, die Kamera kann seitlich angeordnet werden"): MOUNT "landscape" keeps the raw frame upright
# (1280 x 720, 73 x 42 deg on V1.4), "portrait" turns it (720 x 1280). fov: the raw frame's width and
# height in degrees.
MODULES = {
    "v1.4": {"sensor": "SC101IOT", "raw": (1280, 720), "fps": 15, "fov": (73.0, 42.0)},  # docs H 73 / V 42, 3.1 mm F1.8
    "v1.2": {"sensor": "OV3640", "raw": (1024, 768), "fps": 25, "fov": (56.7, 44.1)},    # docs 68 diagonal
}
MAC_SIZE, MAC_HFOV = (1920, 1080), 70.0  # the Mac's picture; its field of view is an estimate (cam_twin.py)


MOUNT = "landscape"  # --mount; main() sets it


def view_crop(uw: int, uh: int) -> tuple[float, float, int] | None:
    """The part of an upright uw x uh frame that becomes the W x H view, as main/camera.c view_crop()
    takes it: the smallest PPA step n/16 (the widest view) at which a centred W x H band fits, so the
    band is (W x 16/n) x (H x 16/n). V1.4 landscape: 1280 x 716.8 at 5/16 (all of its 720 rows but
    one view row); V1.2 landscape: 914 x 512 at 7/16 (the board takes 916, an even width); portrait
    (both): 711 x 398 at 9/16 (the board: 712 x 400, of which 224 of 225 rows are kept)."""
    for n in range(1, 17):
        cw, ch = W * 16 / n, H * 16 / n
        if cw <= uw and ch <= uh:
            return cw, ch, n
    return None


def module_view(module: str) -> dict:
    """What the module gives the app: the upright frame, the band taken from it, its angles."""
    m = MODULES[module]
    landscape = MOUNT == "landscape"
    uw, uh = m["raw"] if landscape else (m["raw"][1], m["raw"][0])
    fw, fh = m["fov"] if landscape else (m["fov"][1], m["fov"][0])
    cw, ch, n = view_crop(uw, uh)
    if (uw - cw) * n / 16 < 1.001 and (uh - ch) * n / 16 < 1.001:
        cw, ch = uw, uh  # at most one view row short of the whole frame (V1.4: 225 rows, 224 kept): all of it
    tw = math.tan(math.radians(fw / 2)) * cw / uw
    th = math.tan(math.radians(fh / 2)) * ch / uh
    return {**m, "module": module, "upright": (uw, uh), "crop": (cw, ch), "step": n,
            "deg": (math.degrees(2 * math.atan(tw)), math.degrees(2 * math.atan(th))), "tan": (tw, th)}


def view_filter(module: str, fps: int, scale: int = 1, video: bool = True, full: bool = False) -> tuple[str, str]:
    """The ffmpeg filter that makes the app's 16:9 view from a video or the Mac's camera, and a note
    of what it emulates. scale 2: twice the view's size (the detector's, from the Mac camera). full (a
    video): the whole upright frame at DETECT_K of its size, for the detector; app_frame() cuts the view."""
    v = module_view(module)
    uw, uh = v["upright"]
    cw, ch = v["crop"]
    dw, dh = v["deg"]
    band = f"{cw:.0f} x {ch:.0f} at {v['step']}/16, about {dw:.0f} x {dh:.0f} deg"
    if video and full:
        fw, fh = int(uw * DETECT_K) // 2 * 2, int(uh * DETECT_K) // 2 * 2
        vf = (f"fps={fps},scale={uw}:{uh}:force_original_aspect_ratio=increase,crop={uw}:{uh},"
              f"scale={fw}:{fh}:flags=area")
        return vf, f"upright {uw} x {uh} to the detector at {fw} x {fh}, the view {band}"
    if video:
        vf = (f"fps={fps},scale={uw}:{uh}:force_original_aspect_ratio=increase,crop={uw}:{uh},"
              f"crop={round(cw)}:{round(ch)},scale={W * scale}:{H * scale}:flags=area")
        return vf, f"upright {uw} x {uh}, the view {band}"
    # The share of the Mac's 16:9 picture that holds the view's angle; as an ffmpeg expression, so it
    # holds whatever size avfoundation opens (1920 x 1080 assumed for the angle).
    mw, mh = MAC_SIZE
    m_th = math.tan(math.radians(MAC_HFOV / 2))
    k = min(1.0, v["tan"][0] / m_th, v["tan"][1] / (m_th * mh / mw))
    deg = math.degrees(2 * math.atan(m_th * k))
    vf = (f"fps={fps},crop='trunc(iw*{k:.4f}/2)*2':'trunc(ih*{k:.4f}/2)*2',"
          f"scale={W * scale}:{H * scale}:flags=area")
    return vf, f"Mac {k:.0%} of its picture, about {deg:.0f} deg wide (module view {dw:.0f})"


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
    bx = 0.10 + 0.02 * math.sin(t * 0.5)  # laid out for the 16:9 view
    objs = [("Singing bowl", bx, 0.44, 0.30, 0.44, 0.90 + 0.05 * math.sin(t * 1.3))]
    objs.append(("Tuning fork", 0.53, 0.20 + 0.03 * math.sin(t * 0.8), 0.09, 0.58, 0.78 + 0.08 * math.sin(t * 0.9)))
    if math.sin(t * 0.25 - 2.0) > -0.3:  # the chimes leave the picture now and then (in view 7 to 21 s)
        objs.append(("Chimes", 0.76, 0.05, 0.11, 0.42, 0.71 + 0.06 * math.sin(t * 1.7)))
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

def ffmpeg_camera(device: str, fps: int, video: str | None = None, scale: int = 1,
                  module: str = "v1.4", full: bool = False) -> subprocess.Popen:
    """Frames of the module's 16:9 view (view_filter); scale 2 gives the detector twice the size,
    full a video's whole upright frame (app_frame() makes the app's view from either)."""
    vf, _ = view_filter(module, fps, scale, video=bool(video), full=full)
    # A video file instead of the camera: in real time, looped, its sound left to chakra_feed.py.
    src = ["-re", "-stream_loop", "-1", "-i", video, "-an"] if video else \
        ["-f", "avfoundation", "-framerate", "30", "-i", f"{device}:none"]
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", *src, "-vf", vf, "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def app_frame(jpeg: bytes, crop: tuple[float, float] | None = None) -> bytes:
    """The view's exact W x H from a bigger frame: the view at twice its size (crop None), or the
    whole upright frame, of which crop (the band's share of width and height, module_view) is cut
    from the centre, as the board takes it."""
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(jpeg)).convert("RGB")
    if crop and crop != (1.0, 1.0):
        cw, ch = img.width * crop[0], img.height * crop[1]
        left, top = (img.width - cw) / 2, (img.height - ch) / 2
        img = img.crop((round(left), round(top), round(left + cw), round(top + ch)))
    out = BytesIO()
    img.resize((W, H), Image.LANCZOS).save(out, "JPEG", quality=85)
    return out.getvalue()


def to_view(boxes, crop: tuple[float, float]):
    """Boxes found in the whole upright frame (normalised to it) moved into the centred band the
    screen shows; crop is the band's share of the frame's width and height (module_view). The
    identity where the band is the whole frame (V1.4 landscape). Otherwise the axes are shifted and
    stretched, a box is clipped to the view, and one less than a third inside is dropped."""
    if boxes is None or crop == (1.0, 1.0):
        return boxes
    xs, ys = crop
    x0s, y0s = (1 - xs) / 2, (1 - ys) / 2  # the band's start, as shares of the frame
    out = []
    for b in boxes:
        bx0, bx1 = (b[1] - x0s) / xs, (b[1] + b[3] - x0s) / xs
        by0, by1 = (b[2] - y0s) / ys, (b[2] + b[4] - y0s) / ys
        cx0, cx1, cy0, cy1 = max(0.0, bx0), min(1.0, bx1), max(0.0, by0), min(1.0, by1)
        if cx1 <= cx0 or cy1 <= cy0 or (cx1 - cx0) * (cy1 - cy0) < (bx1 - bx0) * (by1 - by0) / 3:
            continue
        out.append((b[0], cx0, cy0, cx1 - cx0, cy1 - cy0, *b[5:]))
    return out


def crop_share(module: str) -> tuple[float, float]:
    """The view's band as shares of the upright frame's width and height."""
    v = module_view(module)
    return v["crop"][0] / v["upright"][0], v["crop"][1] / v["upright"][1]


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
            + (f"\t{int(b[6])}" if len(b) > 6 else "") + "\n" for b in boxes[:7])
    app.send(lines)


def run_camera(app: App, files: FrameFile, device: str, stub: StubBoxes | None, video: str | None = None,
               module: str = "v1.4") -> None:
    told = False
    while not app.closed:
        if not app.on:
            app.changed.wait(1.0)
            app.changed.clear()
            continue
        app.changed.clear()
        fps = app.fps
        # OWL-ViT found the bowls at 0.05 in the former 368 x 276 view and at 0.2 to 0.4 in twice that
        # (25.10.2026, the owner's video): the detector gets more pixels, the app its own.
        big = isinstance(stub, Detector)
        # With a video the detector sees the whole upright frame (the former square cut the ends of a
        # row of bowls, 25.10.2026); landscape V1.4 shows all of it now too.
        full = big and bool(video)
        proc = ffmpeg_camera(device, fps, video, 2 if big else 1, module, full)
        print(f"{'video ' + os.path.basename(video) if video else 'camera open: ' + device}, {fps} fps, "
              f"module {module}: {view_filter(module, fps, video=bool(video))[1]}", flush=True)
        n = 0
        for jpeg in jpeg_frames(proc):
            n += 1
            boxes = stub.boxes(jpeg, app.heard) if big else stub.boxes() if stub else None
            if full:
                boxes = to_view(boxes, crop_share(module))
            send_frame(app, files, app_frame(jpeg, crop_share(module) if full else None) if big else jpeg, boxes)
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
    ap.add_argument("--module", choices=sorted(MODULES), default="v1.4",
                    help="the camera module to emulate: v1.4 SC101IOT (default) or v1.2 OV3640")
    ap.add_argument("--mount", choices=["landscape", "portrait"], default="landscape",
                    help="how the module is mounted: landscape 1280 x 720 (default) or portrait 720 x 1280")
    ap.add_argument("--wait", action="store_true", help="retry for 2 min until the simulator listens")
    ap.add_argument("--dry-run", action="store_true", help="say what would happen, open nothing")
    a = ap.parse_args()
    global MOUNT
    MOUNT = a.mount
    mod = MODULES[a.module]
    emulated = f"{mod['sensor']} {a.module} emulated"
    # The source line names what the board would have: the module, emulated from a video or the Mac.
    source = f"Demo scene · {W} × {H}" if a.demo else f"Video · {emulated}" if a.video else f"Mac · {emulated}"
    if a.video and not os.path.exists(a.video):
        sys.exit(f"no such video: {a.video}")
    if a.dry_run:
        vf, note = view_filter(a.module, 2, 2 if a.detect else 1, video=bool(a.video))
        what = ("a drawn demo scene" if a.demo else
                f"ffmpeg {'video' if a.video else 'avfoundation ' + repr(a.device)} -vf {vf} ({note})") + \
            (" with stub boxes" if a.demo_boxes else ", OWL-ViT boxes" if a.detect else ", no boxes")
        print(f"would connect to 127.0.0.1:{a.port}, send 'source {source}', then {what}, "
              f"one {W} x {H} JPEG in a private temp folder, overwritten per frame")
        return
    if not a.demo and not shutil.which("ffmpeg"):
        sys.exit("ffmpeg missing: brew install ffmpeg")
    app = App(a.port, a.wait)
    kind = "demo" if a.demo else "video" if a.video else "camera"
    app.send(f"source\t{source}" + (" · cloud stub" if cloud_key() else "") + f"\t{kind}\n")
    files = FrameFile()
    print(f"{source}{' (' + os.path.basename(a.video) + ')' if a.video else ''} to 127.0.0.1:{a.port}; "
          f"Ctrl-C stops", flush=True)
    try:
        if a.demo:
            run_demo(app, files, a.demo_boxes)
        else:
            marks = Detector() if a.detect and os.path.exists(Detector.VENV) else StubBoxes() if a.demo_boxes else None
            if a.detect and not isinstance(marks, Detector):
                print("no AI venv: --detect needs ~/Library/Application Support/LeopardCode/chakra/ai_venv_eat", flush=True)
            run_camera(app, files, a.device, marks, a.video, a.module)
    except KeyboardInterrupt:
        pass
    finally:
        files.remove()


if __name__ == "__main__":
    main()
