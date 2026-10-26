#!/usr/bin/env python3
"""Finds the best window of a video for the camera module's picture, before camera_live streams it.

What: takes SAMPLES frames spread over the video, asks OWLv2 (the Mac GPU) for bowls, gongs, mallets
      and hands, and slides a window of the module's aspect (16:9 for V1.4 mounted for landscape) along
      the axis the video has to spare. The window that holds the most instruments wholly inside (bowls
      and gongs count 1, mallets 0.5, hands 0.3, at least two thirds of a box inside) wins; a tie goes
      to the middle. Prints one JSON line: {"fx": 0..1, "fy": 0..1, "score": n, "centre_score": n}, where
      fx, fy place the window between the left/top (0) and right/bottom (1) end. Results are cached per
      video (path, size and time) in the private state folder, so the search runs once.
Why:  owner 26.10.2026: "nimm bei den Videos immer den besten Videoausschnitt, bevor du sie reinstreamst".
      A centre crop of a portrait phone video into 16:9 cut the bowls at the top or bottom off.
Pitfalls:
  * OWLv2 takes about 0.65 s a frame: SAMPLES 8 cost about 6 s once per video.
  * The window stays put for the whole video; a scene that moves a lot gets the best average.
Usage:  AI_VENV/bin/python tools/best_crop.py VIDEO [--aspect 16:9] [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

STATE = Path.home() / "Library/Application Support/LeopardCode/chakra"
CACHE = STATE / "best_crop.json"
SAMPLES, STEPS = 8, 21
WEIGHT = {"bowl": 1.0, "gong": 1.0, "mallet": 0.5, "hand": 0.3}
PROMPTS = {"a metal singing bowl": "bowl", "a white crystal singing bowl": "bowl", "a singing bowl held in a hand": "bowl",
           "a large gong hanging in a frame": "gong", "a felt mallet": "mallet", "a human hand": "hand"}
MIN_SCORE = {"bowl": 0.2, "gong": 0.25, "mallet": 0.15, "hand": 0.2}
MODEL = "google/owlv2-base-patch16-ensemble"


def probe(path: Path) -> tuple[int, int, float]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    d = json.loads(r.stdout)
    s = d["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = next((abs(int(sd.get("rotation", 0))) for sd in s.get("side_data_list", []) if "rotation" in sd), 0)
    if rot in (90, 270):
        w, h = h, w  # phone videos store landscape pixels with a rotation flag; ffmpeg turns them upright
    return w, h, float(d["format"].get("duration", 0) or 0)


def frame(path: Path, t: float):
    from io import BytesIO
    from PIL import Image
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale='if(gt(iw,ih),960,-2)':'if(gt(iw,ih),-2,960)',format=yuvj420p",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"], capture_output=True)
    return Image.open(BytesIO(r.stdout)).convert("RGB") if r.stdout else None


def best_window(boxes_per_frame, src_w: int, src_h: int, aspect: float) -> dict:
    """fx, fy of the window with the most weighted instruments wholly inside (boxes normalised 0..1)."""
    # The window in normalised source coordinates: full along one axis, aspect-limited along the other.
    if src_w / src_h > aspect:
        ww, wh, free = aspect * src_h / src_w, 1.0, "x"
    else:
        ww, wh, free = 1.0, (src_w / aspect) / src_h, "y"

    def score(f: float) -> float:
        x0, y0 = (f * (1 - ww), 0.0) if free == "x" else (0.0, f * (1 - wh))
        total = 0.0
        for boxes in boxes_per_frame:
            for kind, bx, by, bw, bh in boxes:
                ix = max(0.0, min(bx + bw, x0 + ww) - max(bx, x0))
                iy = max(0.0, min(by + bh, y0 + wh) - max(by, y0))
                if ix * iy >= (2 / 3) * bw * bh:
                    total += WEIGHT[kind]
        return total

    steps = [i / (STEPS - 1) for i in range(STEPS)]
    scores = {f: score(f) for f in steps}
    best = max(steps, key=lambda f: (scores[f], -abs(f - 0.5)))
    fx, fy = (best, 0.5) if free == "x" else (0.5, best)
    return {"fx": round(fx, 3), "fy": round(fy, 3), "score": round(scores[best], 1), "centre_score": round(scores[0.5], 1),
            "free": free}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("--aspect", default="16:9")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    num, den = (float(x) for x in a.aspect.split(":"))
    aspect = num / den
    st = a.video.stat()
    key = f"{a.video.resolve()}|{st.st_size}|{int(st.st_mtime)}|{a.aspect}"
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    if key in cache:
        print(json.dumps(cache[key]))
        return
    w, h, dur = probe(a.video)
    if abs(w / h - aspect) < 0.01:
        out = {"fx": 0.5, "fy": 0.5, "score": 0, "centre_score": 0, "free": "none"}
        print(json.dumps(out))
        return
    if a.dry_run:
        print(f"(dry run) {a.video.name}: {w} x {h}, {dur:.0f} s; would look at {SAMPLES} frames for the best {a.aspect} window")
        return
    import torch
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(MODEL)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Owlv2ForObjectDetection.from_pretrained(MODEL).eval().to(dev)
    names = list(PROMPTS)
    text = proc(text=[names], return_tensors="pt")
    per_frame = []
    for i in range(SAMPLES):
        img = frame(a.video, dur * (i + 0.5) / SAMPLES)
        if img is None:
            continue
        with torch.no_grad():
            pix = proc(images=img, return_tensors="pt")
            r = model(input_ids=text["input_ids"].to(dev), attention_mask=text["attention_mask"].to(dev),
                      pixel_values=pix["pixel_values"].to(dev))
            r.logits, r.pred_boxes = r.logits.cpu(), r.pred_boxes.cpu()
            side = max(img.size)
            post = proc.image_processor.post_process_object_detection(r, threshold=0.15,
                                                                      target_sizes=torch.tensor([[side, side]]))[0]
        boxes = []
        for s, lab, b in zip(post["scores"].tolist(), post["labels"].tolist(), post["boxes"].tolist()):
            kind = PROMPTS[names[lab]]
            if s >= MIN_SCORE[kind]:
                x0, y0 = max(0.0, b[0]) / img.width, max(0.0, b[1]) / img.height
                x1, y1 = min(img.width, b[2]) / img.width, min(img.height, b[3]) / img.height
                if x1 > x0 and y1 > y0:
                    boxes.append((kind, x0, y0, x1 - x0, y1 - y0))
        per_frame.append(boxes)
    out = best_window(per_frame, w, h, aspect)
    cache[key] = out
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
