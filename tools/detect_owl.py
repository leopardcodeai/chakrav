#!/usr/bin/env python3
"""Marks instruments in camera frames with OWLv2 (or OWL-ViT), an open-vocabulary detector, on the Mac.

What: reads frames on stdin, each as a 4-byte big-endian length, one signed byte with the chakra the app
      hears now (-1 none) and a JPEG, and answers each at once with one JSON line on stdout:
      [[label, x, y, w, h, score, played], ...], normalised 0..1, at most 4. The model looks for the
      words in LABELS (zero-shot: no training on our instruments), keeps boxes over THRESHOLD and drops a
      box that overlaps a better one of the same label by more than half. It runs in its own thread on
      the newest frame it is asked for, so a slow model never holds the picture up; bowl_tracker.py
      answers every frame from what it keeps (bowls stay bowls and stay where they are), asks for a new
      detection only when needed (every 4th frame in a still scene), marks a bowl played when it moves,
      a hand or mallet covers it or its learned note sounds, drops a "bowl" found on a foot or a head,
      and labels a bowl with its note ("Bowl C") once heard and seen together.
      camera_live.py --detect runs it.
Why:  owner 25.10.2026: "teste in ChakraV, dann sehe ich, wie erkannt wird, auch mit Markierung";
      and "muss ja nicht jedes Frame komplett neu bewerten", the mallet and the sound as hints.
      The first real detector, before a trained ESPDet-Pico on the ESP32-S31.
Measured 25.10.2026 on the owner's video, the view's crop at 736 x 552, Mac GPU (MPS):
      OWL-ViT B/32  75 ms, bowls at 0.12 to 0.24, nothing at all while a person is in the picture,
                    a foot taken for a bowl;
      OWLv2 B/16    650 ms, bowls at 0.3 to 0.44, all five with a person in the picture, the foot a foot.
      So OWLv2 is the default; --model owlvit for the fast one.
Pitfalls:
  * OWLv2 pads the picture to a square: its boxes are scaled by the longer side.
  * On the CPU OWLv2 takes several seconds a detection; the tracker still answers every frame.
  * Needs the venv with torch and transformers (~/Library/Application Support/LeopardCode/chakra/
    ai_venv_eat); the models (600 MB, 620 MB) are in the Hugging Face cache after the first run.
Usage:  camera_live.py --detect ...                 (normally)
        detect_owl.py [--model owlv2|owlvit] [--dry-run]
"""
import argparse
import io
import json
import struct
import sys
import threading
from pathlib import Path

# Prompts as phrases: "gong" alone pulled every metal bowl (25.10.2026, the owner's chakra bowls).
# Hand, foot, leg and head are helpers for the tracker: a hand plays a bowl, a foot, a leg or a head is no bowl
# (a leg was taken for a rainstick, 25.10.2026).
SHOW = {"a metal singing bowl": "Singing bowl", "a large gong hanging in a frame": "Gong", "a hand drum": "Drum",
        "a felt mallet": "Mallet", "a tuning fork": "Tuning fork", "wind chimes": "Chimes", "a rainstick": "Rainstick",
        "a human hand": "Hand", "a bare foot": "Foot", "a human leg": "Leg", "a person's head": "Head"}
LABELS = list(SHOW)
# Zero-shot is weak on the rarer instruments: a leg came out as a rainstick and a mallet's handle as a
# tuning fork at 0.10 to 0.18 (25.10.2026, OWLv2), real bowls at 0.3 to 0.44. These need more.
MIN_SCORE = {"Rainstick": 0.2, "Tuning fork": 0.2, "Drum": 0.2, "Chimes": 0.2, "Gong": 0.15}
THRESHOLD, FIND_BOXES = 0.10, 16  # up to 16 found (helpers included); the tracker keeps them, the app draws 7
MODELS = {"owlv2": "google/owlv2-base-patch16-ensemble", "owlvit": "google/owlvit-base-patch32"}


def iou(a, b) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    w, h = max(0.0, min(ax2, bx2) - max(a[0], b[0])), max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = w * h
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


class MalletColour:
    """The mallet's head by its colour: learned from the model's mallet box, then followed every frame.
    The model finds a mallet only now and then; its felt head (red on the owner's) is easy to follow by
    hue, which is cheap enough for the ESP32-S31 too. Pixels of that hue that stay put (a red stripe on
    the mat) become background and do not count."""
    HUE_TOL, MIN_PX = 15.0, 4

    def __init__(self, np):
        self.np = np
        self.hue = None
        self.bg = None

    def hsv(self, img):
        np = self.np
        a = np.asarray(img.convert("HSV").resize((img.width // 4, img.height // 4)), dtype=np.float32)
        return a[..., 0] * 360 / 255, a[..., 1] / 255, a[..., 2] / 255

    def learn(self, img, box) -> None:
        np = self.np
        h, s, v = self.hsv(img)
        H, W = h.shape
        x0, y0 = int(box[0] * W), int(box[1] * H)
        x1, y1 = max(x0 + 1, int((box[0] + box[2]) * W)), max(y0 + 1, int((box[1] + box[3]) * H))
        hh, ss, vv = h[y0:y1, x0:x1], s[y0:y1, x0:x1], v[y0:y1, x0:x1]
        m = (ss > 0.5) & (vv > 0.3)
        if m.sum() < 15:
            return  # a grey or wooden mallet: nothing to follow by colour
        rad = np.radians(hh[m])
        hue = float(np.degrees(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360)
        self.hue = hue if self.hue is None else hue  # the newest mallet box decides

    def find(self, img):
        """(x, y) of the head this frame, normalised, or None."""
        if self.hue is None:
            return None
        np = self.np
        h, s, v = self.hsv(img)
        d = np.abs((h - self.hue + 180) % 360 - 180)
        m = (d < self.HUE_TOL) & (s > 0.5) & (v > 0.3)
        self.bg = m.astype(np.float32) if self.bg is None or self.bg.shape != m.shape else 0.95 * self.bg + 0.05 * m
        m &= self.bg < 0.6  # what has been there for most of the last ~20 frames is background
        if m.sum() < self.MIN_PX:
            return None
        ys, xs = np.nonzero(m)
        return float(xs.mean() / m.shape[1]), float(ys.mean() / m.shape[0])


class Worker:
    """The model in its own thread: ask() hands it the newest frame, take() returns finished boxes once."""

    def __init__(self, detect):
        self.detect = detect
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.frame = self.result = None
        self.busy = False
        threading.Thread(target=self.run, daemon=True).start()

    def ask(self, img) -> None:
        with self.lock:
            if not self.busy:
                self.frame, self.busy = img, True
                self.wake.set()

    def take(self):
        with self.lock:
            r, self.result = self.result, None
            return r

    def run(self) -> None:
        while True:
            self.wake.wait()
            self.wake.clear()
            boxes = self.detect(self.frame)
            with self.lock:
                self.result, self.busy = boxes, False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", choices=sorted(MODELS), default="owlv2")
    ap.add_argument("--sync", action="store_true", help="detect in the frame's own turn (for tests: same output every run)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    name = MODELS[a.model]
    if a.dry_run:
        print(f"would load {name} and look for {LABELS}")
        return
    import numpy as np
    import torch
    from PIL import Image
    from transformers import (Owlv2ForObjectDetection, Owlv2Processor, OwlViTForObjectDetection,
                              OwlViTProcessor)
    proc_cls, model_cls = (Owlv2Processor, Owlv2ForObjectDetection) if a.model == "owlv2" else \
        (OwlViTProcessor, OwlViTForObjectDetection)
    proc = proc_cls.from_pretrained(name)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"  # the Mac's GPU: several times faster
    model = model_cls.from_pretrained(name).eval().to(dev)
    with torch.no_grad():
        text = proc(text=[LABELS], return_tensors="pt")

    def detect(img):
        """One frame's boxes [(label, x, y, w, h, score)], best first, one per place and label."""
        with torch.no_grad():
            pix = proc(images=img, return_tensors="pt")
            res = model(input_ids=text["input_ids"].to(dev), attention_mask=text["attention_mask"].to(dev),
                        pixel_values=pix["pixel_values"].to(dev))
            res.logits, res.pred_boxes = res.logits.cpu(), res.pred_boxes.cpu()
            side = max(img.width, img.height)  # OWLv2 padded it to a square
            size = [[side, side]] if a.model == "owlv2" else [[img.height, img.width]]
            post = proc.image_processor.post_process_object_detection(res, threshold=THRESHOLD,
                                                                      target_sizes=torch.tensor(size))[0]
        boxes = []
        for score, lab, box in sorted(zip(post["scores"].tolist(), post["labels"].tolist(), post["boxes"].tolist()),
                                      reverse=True):
            x0, y0 = max(0.0, box[0]), max(0.0, box[1])
            x1, y1 = min(float(img.width), box[2]), min(float(img.height), box[3])
            if x1 <= x0 or y1 <= y0:
                continue
            b = (x0 / img.width, y0 / img.height, (x1 - x0) / img.width, (y1 - y0) / img.height)
            label = SHOW[LABELS[lab]]
            if score < MIN_SCORE.get(label, THRESHOLD):
                continue
            if any(o[0] == label and iou(b, o[1:5]) > 0.5 for o in boxes):
                continue
            boxes.append((label, *[round(v, 3) for v in b], round(score, 2)))
            if len(boxes) >= FIND_BOXES:
                break
        return boxes

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import bowl_tracker
    tracker = bowl_tracker.Tracker()
    mallet = MalletColour(np)
    worker = None if a.sync else Worker(detect)
    inp, out = sys.stdin.buffer, sys.stdout
    prev = None  # the last frame in grey, for the motion inside each box
    while True:
        head = inp.read(5)
        if len(head) < 5:
            return
        n, heard = struct.unpack(">Ib", head)
        img = Image.open(io.BytesIO(inp.read(n))).convert("RGB")
        grey = np.asarray(img.convert("L"), dtype=np.float32)
        same = prev is not None and prev.shape == grey.shape
        scene = float(np.abs(grey[::8, ::8] - prev[::8, ::8]).mean()) if same else 0.0
        found = None
        if tracker.need_detect(scene):
            if worker:
                worker.ask(img)
            else:
                found = detect(img)
        if worker:
            found = worker.take()
        if found is not None:
            tracker.detections(found)  # from a frame or two ago: bowls do not move in that time
            for f in found:
                if f[0] == "Mallet" and f[5] >= 0.12:
                    mallet.learn(img, f[1:5])
                    break
        tracker.mallet = mallet.find(img)
        # The motion inside each kept box: a hand or a mallet on a bowl changes its pixels, a still bowl does not.
        H, W = grey.shape
        motions = []
        for t in tracker.tracks:
            x0, y0 = int(max(0.0, t.box[0]) * W), int(max(0.0, t.box[1]) * H)
            x1, y1 = max(x0 + 1, int((t.box[0] + t.box[2]) * W)), max(y0 + 1, int((t.box[1] + t.box[3]) * H))
            motions.append(float(np.abs(grey[y0:y1, x0:x1] - prev[y0:y1, x0:x1]).mean()) if same else 0.0)
        prev = grey
        out.write(json.dumps(tracker.step(motions, heard)) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
