#!/usr/bin/env python3
"""Renders what ChakraV sees in a video as large 16:9 stills: the frame with the app's marks on it.

What: plays VIDEO through the same chain as the simulator, at FPS frames a second: the best 16:9
      window (best_crop.py), the heard chakra from ChakraA's own C detector (Flow, tests/analyse.sh),
      OWLv2 and the tracker (detect_owl.py --sync, bowl_tracker.py). Every EVERY seconds it saves the
      frame at WIDTH x WIDTH*9/16 with the marks drawn like the app draws them: a grey frame and pill
      for a seen instrument, amber for a played one, "Bowl G" once a bowl has its note, and a pill
      with the heard chakra in its colour. Writes OUT/t<seconds>.png (and .json with its marks) and OUT/sheet.png to choose from.
Why:  owner 27.10.2026: a picture of the video detection for the blog; the app's camera view is
      400 x 224 pixels, too small for a page.
Privacy: the stills show the people in the video. Use it only on a video whose people agreed to be
      shown (the owner asked them for player_export.mp4, 27.10.2026); OUT stays in the private state
      folder until the owner picks a still.
Pitfalls:
  * Runs in the AI venv (torch, transformers); OWLv2 on the Mac GPU, about 0.1 to 0.6 s a frame.
  * The tracker needs a few seconds to confirm and name bowls: stills in the first 5 s show little.
      With --clip A B it saves every frame from A to B s instead (OUT/frames/), for an animation.
Usage:  AI_VENV/bin/python tools/render_detection.py VIDEO OUT [--every 6] [--fps 5] [--width 1440]
            [--clip A B] [--dry-run]
"""
import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHAKRA_TOOLS = HERE.parent.parent / "chakra/tools"
CHAKRAS = [("Root", 0xE0262B), ("Sacral", 0xF47A1F), ("Solar plexus", 0xF2B705), ("Heart", 0x2FA84F),
           ("Throat", 0x1E88E5), ("Third eye", 0x4B3FB5), ("Crown", 0x9B3FC8)]
SEEN, PLAYED = (235, 235, 240), (255, 159, 10)  # the app's grey and amber (#FF9F0A)
FONT = "/System/Library/Fonts/Helvetica.ttc"
SHORT = {"Singing bowl": "Bowl"}  # the app's short labels (chakra_core.c LABELS), owner 25.10.2026


def rgb(v: int) -> tuple:
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def window(video: Path) -> str:
    """The ffmpeg crop for the best 16:9 window."""
    r = subprocess.run([sys.executable, str(HERE / "best_crop.py"), str(video)], capture_output=True, text=True)
    c = json.loads(r.stdout.strip().splitlines()[-1])
    if c["free"] == "x":
        return f"crop=ih*16/9:ih:(iw-ih*16/9)*{c['fx']}:0"
    if c["free"] == "y":
        return f"crop=iw:iw*9/16:0:(ih-iw*9/16)*{c['fy']}"
    return "null"


def heard_timeline(video: Path) -> list:
    sys.path.insert(0, str(CHAKRA_TOOLS))
    import light_timeline
    names = [n for n, _ in CHAKRAS]
    return [(a, b, names.index(n)) for a, b, n in light_timeline.timeline(video, "flow") if n in names]


def heard_at(tl: list, t: float) -> int:
    return next((k for a, b, k in tl if a <= t < b), -1)


def draw(img, marks, heard: int, width: int):
    from PIL import ImageDraw, ImageFont
    s = width / 400  # the app's camera view is 400 px wide: scale its strokes and pills
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(FONT, int(10 * s * 1.1))
    W, H = img.size
    for label, x, y, w, h, _steady, played in marks:
        label = SHORT.get(label, label)
        col = PLAYED if played else SEEN
        x0, y0, x1, y1 = x * W, y * H, (x + w) * W, (y + h) * H
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(2 * s), outline=col + (255,), width=max(2, int(1.2 * s)))
        tw = d.textlength(label, font=font)
        ph, pw = int(14 * s), int(tw + 14 * s)
        px = min(x0, W - pw)
        py = y0 - ph - 2 if y0 - ph - 2 > 0 else y0 + 2
        d.rounded_rectangle([px, py, px + pw, py + ph], radius=ph // 2, fill=col + (235,))
        d.text((px + 7 * s, py + ph / 2), label, font=font, fill=(20, 20, 24), anchor="lm")
    if heard >= 0:
        name, c = CHAKRAS[heard]
        big = ImageFont.truetype(FONT, int(16 * s))
        tw = d.textlength(name, font=big)
        ph, pw = int(26 * s), int(tw + 46 * s)
        x, y = int(10 * s), H - ph - int(10 * s)
        d.rounded_rectangle([x, y, x + pw, y + ph], radius=ph // 2, fill=(20, 18, 28, 220))
        r = 6 * s
        d.ellipse([x + 12 * s, y + ph / 2 - r, x + 12 * s + 2 * r, y + ph / 2 + r], fill=rgb(c))
        d.text((x + 32 * s, y + ph / 2), name, font=big, fill=(255, 255, 255), anchor="lm")
    return img


def sheet(out: Path, files: list) -> None:
    from PIL import Image, ImageDraw, ImageFont
    W, pad, cols = 420, 8, 4
    rows = (len(files) + cols - 1) // cols
    th = W * 9 // 16
    sh = Image.new("RGB", (cols * (W + pad) + pad, rows * (th + pad + 26) + pad), "#1c1c1e")
    d, font = ImageDraw.Draw(sh), ImageFont.truetype(FONT, 20)
    for i, f in enumerate(files):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (th + pad + 26)
        sh.paste(Image.open(f).convert("RGB").resize((W, th)), (x, y + 26))
        d.text((x, y + 2), f.stem, fill="white", font=font)
    sh.save(out / "sheet.png")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--every", type=float, default=6.0)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--clip", type=float, nargs=2, metavar=("A", "B"), help="every frame from A to B s")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        print(f"(dry run) {a.video.name}: frames at {a.fps}/s through OWLv2 and the tracker, a still every "
              f"{a.every} s at {a.width} px wide into {a.out}")
        return
    from io import BytesIO

    from PIL import Image
    sys.path.insert(0, str(Path.home() / "Coding/company/tools"))
    try:
        import progress
    except ImportError:
        progress = None
    a.out.mkdir(parents=True, exist_ok=True)
    crop, tl = window(a.video), heard_timeline(a.video)
    W, H = a.width, a.width * 9 // 16
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(a.video)], capture_output=True, text=True).stdout.strip() or 0)
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(a.video), "-vf",
                           f"{crop},fps={a.fps},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          stdout=subprocess.PIPE)
    det = subprocess.Popen([sys.executable, str(HERE / "detect_owl.py"), "--sync"], stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    total = int((a.clip[1] if a.clip else dur) * a.fps)
    if a.clip:
        (a.out / "frames").mkdir(exist_ok=True)
    bar = progress.Bar("Detection stills", total=total, unit="frames") if progress else None
    files, i, next_still = [], 0, a.every
    while True:
        raw = ff.stdout.read(W * H * 3)
        if len(raw) < W * H * 3:
            break
        t = i / a.fps
        frame = Image.frombytes("RGB", (W, H), raw)
        buf = BytesIO()
        frame.resize((960, 540)).save(buf, "JPEG", quality=85)
        heard = heard_at(tl, t)
        det.stdin.write(struct.pack(">Ib", buf.tell(), heard) + buf.getvalue())
        det.stdin.flush()
        marks = json.loads(det.stdout.readline())
        if a.clip:
            if t > a.clip[1]:
                break
            if t >= a.clip[0]:
                draw(frame, marks, heard, W).save(a.out / "frames" / f"f{i:05d}.png")
        elif t >= next_still:
            f = a.out / f"t{int(t):03d}.png"
            draw(frame, marks, heard, W).save(f)
            f.with_suffix(".json").write_text(json.dumps({"t": t, "heard": heard, "marks": marks}))
            files.append(f)
            next_still += a.every
        i += 1
        if bar:
            bar.advance()
    det.stdin.close()
    if bar:
        bar.done()
    ff.kill()
    if a.clip:
        print(f"frames {a.clip[0]} to {a.clip[1]} s in {a.out / 'frames'}")
        return
    sheet(a.out, files)
    print(f"{len(files)} stills and sheet.png in {a.out}")


if __name__ == "__main__":
    main()
