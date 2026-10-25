#!/usr/bin/env python3
"""Marks instruments in camera frames with OWL-ViT, an open-vocabulary detector, on the Mac.

What: reads frames on stdin, each as a 4-byte big-endian length and a JPEG, and answers each with
      one JSON line on stdout: [[label, x, y, w, h, score], ...], normalised 0..1, at most MAX_BOXES,
      best first. It looks for the words in LABELS (google/owlvit-base-patch32, zero-shot: no
      training on our instruments), keeps boxes over THRESHOLD and drops a box that overlaps a
      better one of the same label by more than half. camera_live.py --detect runs it.
Why:  owner 25.10.2026: "teste in ChakraV, dann sehe ich, wie erkannt wird, auch mit Markierung".
      The first real detector, before a trained ESPDet-Pico on the ESP32-S31.
Pitfalls:
  * On the Mac's GPU (MPS) a frame takes well under a second; on the CPU about 2 s, too slow for 2 fps.
  * Zero-shot: bowls are found well, "gong" and "mallet" less so; a trained detector on your own
    labelled frames is the next step.
  * Needs the venv with torch and transformers (~/Library/Application Support/LeopardCode/chakra/
    ai_venv_eat); the model (about 600 MB) is in the Hugging Face cache after the first run.
Usage:  camera_live.py --detect ...      (normally)
        detect_owl.py --dry-run          says what it would load
"""
import argparse
import io
import json
import struct
import sys

# Prompts as phrases: "gong" alone pulled every metal bowl (25.10.2026, the owner's chakra bowls).
LABELS = ["a metal singing bowl", "a large gong hanging in a frame", "a hand drum", "a felt mallet",
          "a tuning fork", "wind chimes", "a rainstick"]
SHOW = {"a metal singing bowl": "Singing bowl", "a large gong hanging in a frame": "Gong", "a hand drum": "Drum",
        "a felt mallet": "Mallet", "a tuning fork": "Tuning fork", "wind chimes": "Chimes", "a rainstick": "Rainstick"}
THRESHOLD, MAX_BOXES = 0.10, 4
MODEL = "google/owlvit-base-patch32"


def iou(a, b) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    w, h = max(0.0, min(ax2, bx2) - max(a[0], b[0])), max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = w * h
    return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-9)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        print(f"would load {MODEL} and look for {LABELS}")
        return
    import torch
    from PIL import Image
    from transformers import OwlViTForObjectDetection, OwlViTProcessor
    proc = OwlViTProcessor.from_pretrained(MODEL)
    dev = "mps" if torch.backends.mps.is_available() else "cpu"  # the Mac's GPU: several times faster
    model = OwlViTForObjectDetection.from_pretrained(MODEL).eval().to(dev)
    with torch.no_grad():
        text = proc(text=[LABELS], return_tensors="pt")
    inp, out = sys.stdin.buffer, sys.stdout
    while True:
        head = inp.read(4)
        if len(head) < 4:
            return
        (n,) = struct.unpack(">I", head)
        img = Image.open(io.BytesIO(inp.read(n))).convert("RGB")
        with torch.no_grad():
            pix = proc(images=img, return_tensors="pt")
            res = model(input_ids=text["input_ids"].to(dev), attention_mask=text["attention_mask"].to(dev),
                        pixel_values=pix["pixel_values"].to(dev))
            res.logits, res.pred_boxes = res.logits.cpu(), res.pred_boxes.cpu()
            post = proc.image_processor.post_process_object_detection(res, threshold=THRESHOLD,
                                                      target_sizes=torch.tensor([[img.height, img.width]]))[0]
        boxes = []
        for score, lab, box in sorted(zip(post["scores"].tolist(), post["labels"].tolist(), post["boxes"].tolist()),
                                      reverse=True):
            x0, y0, x1, y1 = box
            b = (max(0.0, x0 / img.width), max(0.0, y0 / img.height), (x1 - x0) / img.width, (y1 - y0) / img.height)
            name = SHOW[LABELS[lab]]
            if any(o[0] == name and iou(b, o[1:5]) > 0.5 for o in boxes):
                continue
            boxes.append([name, *[round(v, 3) for v in b], round(score, 2)])
            if len(boxes) >= MAX_BOXES:
                break
        out.write(json.dumps(boxes) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
