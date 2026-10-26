#!/usr/bin/env python3
"""Builds the training set for ChakraV's own instrument detector: frames with boxes proposed by OWLv2.

What: takes a frame every STEP seconds from the owner's videos (own_media/chakrav_training, own_media/one)
      and the downloaded YouTube videos (youtube/), drops frames that barely differ from the last kept one,
      asks OWLv2 (google/owlv2-base-patch16-ensemble, zero-shot, the Mac GPU) for bowls, mallets, hands and
      gongs, and writes the set in YOLO format into the private state folder:
        detector_data/images/{train,val}/<video>_<t>.jpg   long side 640
        detector_data/labels/{train,val}/<video>_<t>.txt   class cx cy w h, normalised
        detector_data/data.yaml                             class names, for the trainer
        detector_data/review/<video>.jpg                    a sheet of frames with the boxes drawn, to check by eye
      Train and val are split by video (every fifth video to val), so val never sees a training video.
      Classes: 0 bowl (metal and crystal), 1 mallet, 2 hand, 3 gong.
Why:  owner 26.10.2026: "ja" to a detector trained on his own pictures (ESPDet-Pico for the S31); OWLv2 alone
      found 2 or 3 of many bowls in a dim session, and 7 of 7 on bright ones. Its boxes on the good frames
      are the first labels; a person checks them on the review sheets before training.
Privacy: the owner's videos show people at sessions. Frames, labels and sheets stay in the private state
      folder (0700), are never committed, uploaded or sent to a cloud model. Videos marked "none" or
      "audio only" in own_events.json, and those named in own_media/_excluded/names.txt, are skipped.
Pitfalls:
  * Proposed boxes are a teacher's guesses: a bowl at 0.25 is often right, a mallet at 0.15 often not;
    the thresholds per class are below. The review sheets are the check.
  * 360-degree "little planet" videos are too distorted to teach a normal camera; they are skipped.
  * OWLv2 takes about 0.65 s a frame on the Mac GPU; 2000 frames take about 20 minutes.
Usage:  AI_VENV/bin/python tools/make_detector_data.py [--step 2] [--max-per-video 80] [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Coding/company/tools"))
try:
    import progress
except ImportError:
    progress = None

STATE = Path.home() / "Library/Application Support/LeopardCode/chakra"
OWN = [STATE / "own_media/chakrav_training", STATE / "own_media/one"]
YOUTUBE = STATE / "youtube"
OUT = STATE / "detector_data"
EVENTS = STATE / "own_media/own_events.json"
EXCLUDED = STATE / "own_media/_excluded/names.txt"
VIDEO = (".mov", ".mp4", ".m4v")
CLASSES = ["bowl", "mallet", "hand", "gong"]
PROMPTS = {"a metal singing bowl": 0, "a white crystal singing bowl": 0, "a felt mallet": 1, "a wooden stick mallet": 1,
           "a human hand": 2, "a large gong hanging in a frame": 3}
MIN_SCORE = {0: 0.25, 1: 0.18, 2: 0.22, 3: 0.30}  # per class: bowls score 0.3 to 0.44 when right (25.10.2026)
LONG_SIDE = 640
SAME = 3.0  # mean change (0..255) under which a frame counts as the same as the last kept one
MODEL = "google/owlv2-base-patch16-ensemble"


def videos() -> list[Path]:
    events = json.loads(EVENTS.read_text()) if EVENTS.exists() else {}
    skip = set(EXCLUDED.read_text().split()) if EXCLUDED.exists() else set()
    out, seen = [], set()
    for d in OWN + [YOUTUBE]:
        for p in sorted(d.iterdir()) if d.exists() else []:
            if p.suffix.lower() not in VIDEO or p.name in skip or p.name in seen:
                continue
            use = str(events.get(p.name, {}).get("use", ""))
            if use.startswith("none") or use.startswith("audio only") or "distorted" in use:
                continue
            seen.add(p.name)
            out.append(p)
    return out


def frames(path: Path, step: float):
    """(t, PIL image) every step seconds, scaled to LONG_SIDE."""
    from io import BytesIO
    from PIL import Image
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vf",
                             f"fps=1/{step:g},scale='if(gt(iw,ih),{LONG_SIDE},-2)':'if(gt(iw,ih),-2,{LONG_SIDE})',format=yuvj420p",
                             "-q:v", "3", "-f", "image2pipe", "-vcodec", "mjpeg", "-"], stdout=subprocess.PIPE)
    buf, i = b"", 0
    try:
        while True:
            chunk = proc.stdout.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                a = buf.find(b"\xff\xd8")
                b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
                if a < 0 or b < 0:
                    break
                yield i * step, Image.open(BytesIO(buf[a:b + 2])).convert("RGB")
                buf, i = buf[b + 2:], i + 1
    finally:
        proc.kill()  # stopped early at --max-per-video: end ffmpeg quietly instead of a broken pipe
        proc.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--step", type=float, default=2.0, help="seconds between frames")
    ap.add_argument("--max-per-video", type=int, default=80)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    vids = videos()
    if a.dry_run:
        for v in vids:
            print(v.parent.name, v.name)
        print(f"(dry run) {len(vids)} videos, a frame every {a.step:g} s, at most {a.max_per_video} each, into {OUT}")
        return
    import numpy as np
    import torch
    from PIL import ImageDraw
    from transformers import Owlv2ForObjectDetection, Owlv2Processor
    proc = Owlv2Processor.from_pretrained(MODEL)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    model = Owlv2ForObjectDetection.from_pretrained(MODEL).eval().to(dev)
    names = list(PROMPTS)
    text = proc(text=[names], return_tensors="pt")
    for sub in ("images/train", "images/val", "labels/train", "labels/val", "review"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    OUT.chmod(0o700)
    (OUT / "data.yaml").write_text(f"path: {OUT}\ntrain: images/train\nval: images/val\nnames:\n" +
                                   "".join(f"  {i}: {n}\n" for i, n in enumerate(CLASSES)))
    bar = progress.Bar("Detector data", total=len(vids), unit="videos") if progress else None
    summary = {}
    for vi, v in enumerate(vids):
        split = "val" if vi % 5 == 4 else "train"
        stem = v.stem.replace(" ", "_")
        if (OUT / "done" / stem).exists():
            if bar:
                bar.advance()
            continue  # done in an earlier run
        prev, kept, sheet, n_boxes = None, 0, [], [0] * len(CLASSES)
        for t, img in frames(v, a.step):
            grey = np.asarray(img.convert("L").resize((80, 80)), dtype=np.float32)
            if prev is not None and float(np.abs(grey - prev).mean()) < SAME:
                continue
            prev = grey
            with torch.no_grad():
                pix = proc(images=img, return_tensors="pt")
                r = model(input_ids=text["input_ids"].to(dev), attention_mask=text["attention_mask"].to(dev),
                          pixel_values=pix["pixel_values"].to(dev))
                r.logits, r.pred_boxes = r.logits.cpu(), r.pred_boxes.cpu()
                side = max(img.size)
                post = proc.image_processor.post_process_object_detection(r, threshold=0.15,
                                                                          target_sizes=torch.tensor([[side, side]]))[0]
            lines, boxes = [], []
            for score, lab, box in zip(post["scores"].tolist(), post["labels"].tolist(), post["boxes"].tolist()):
                c = PROMPTS[names[lab]]
                if score < MIN_SCORE[c]:
                    continue
                x0, y0 = max(0.0, box[0]), max(0.0, box[1])
                x1, y1 = min(float(img.width), box[2]), min(float(img.height), box[3])
                if x1 - x0 < 8 or y1 - y0 < 8:
                    continue
                if any(c == oc and min(x1, ox1) - max(x0, ox0) > 0.6 * (x1 - x0) and min(y1, oy1) - max(y0, oy0) > 0.6 * (y1 - y0)
                       for oc, ox0, oy0, ox1, oy1 in boxes):
                    continue  # the same object twice (two prompts for one bowl)
                boxes.append((c, x0, y0, x1, y1))
                lines.append(f"{c} {(x0 + x1) / 2 / img.width:.4f} {(y0 + y1) / 2 / img.height:.4f} "
                             f"{(x1 - x0) / img.width:.4f} {(y1 - y0) / img.height:.4f}")
            if not boxes:
                continue  # frames without any instrument teach little and cost review time
            name = f"{stem}_{int(round(t * 1000)):08d}"  # milliseconds: --step under 1 s must not overwrite
            img.save(OUT / "images" / split / f"{name}.jpg", quality=90)
            (OUT / "labels" / split / f"{name}.txt").write_text("\n".join(lines) + "\n")
            for b in boxes:
                n_boxes[b[0]] += 1
            if len(sheet) < 12 and kept % 3 == 0:
                d = img.copy()
                dr = ImageDraw.Draw(d)
                for c, x0, y0, x1, y1 in boxes:
                    dr.rectangle([x0, y0, x1, y1], outline=["#FFD60A", "#FF453A", "#64D2FF", "#BF5AF2"][c], width=3)
                sheet.append(d.resize((d.width // 2, d.height // 2)))
            kept += 1
            if kept >= a.max_per_video:
                break
        if sheet:
            from PIL import Image
            w, h = sheet[0].size
            grid = Image.new("RGB", (w * 4, h * ((len(sheet) + 3) // 4)))
            for k, s in enumerate(sheet):
                grid.paste(s.resize((w, h)), ((k % 4) * w, (k // 4) * h))
            grid.save(OUT / "review" / f"{stem}.jpg", quality=80)
        (OUT / "done").mkdir(exist_ok=True)
        (OUT / "done" / stem).write_text(str(kept))  # only a finished video counts as done; a crash redoes it
        summary[v.name] = {"split": split, "frames": kept, **{CLASSES[i]: n for i, n in enumerate(n_boxes)}}
        print(f"{v.name}: {split}, {kept} frames, " + ", ".join(f"{CLASSES[i]} {n}" for i, n in enumerate(n_boxes)), flush=True)
        if bar:
            bar.advance()
    if bar:
        bar.done()
    old = json.loads((OUT / "summary.json").read_text()) if (OUT / "summary.json").exists() else {}
    (OUT / "summary.json").write_text(json.dumps({**old, **summary}, indent=1))
    print(OUT)


if __name__ == "__main__":
    main()
