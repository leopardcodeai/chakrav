#!/usr/bin/env python3
"""Measures the ChakraV detect Space on Hugging Face ZeroGPU: round trip and GPU time per model.

What: waits until the Space (SPACE, cloud/hf_space/) is RUNNING, then sends the same frame to every
      model ROUNDS times through the Gradio API and prints per call: the round trip from this Mac,
      the model's own GPU time and the best boxes; at the end the median per model.
Why:  owner 25.10.2026: run open models on a free GPU "statt Paid-API-Weg", verified with real
      measurements, then wire them into the ESP32-S31 simulator.
Pitfalls:
  * The first call after a pause is a cold start (the GPU slot is attached per call on ZeroGPU);
    the medians are taken over the later calls.
  * Needs HF_TOKEN_WRITE (or HF_TOKEN) in the environment (a login shell), never on the command line.
  * Send only frames that may leave the Mac (demo scene, Commons videos): the Space is public code.
Usage:  /bin/zsh -lc 'AI_VENV/bin/python tools/hf_detect_bench.py FRAME.jpg [--rounds 3]'
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request

SPACE = "CapLeo123/stackfuel_test"
MODELS = ["owlvit-b32", "owlv2-b16", "gdino-tiny"]
PROMPTS = "a metal singing bowl, a large gong hanging in a frame, a hand drum, a felt mallet, a person"


def token() -> str:
    t = os.environ.get("HF_TOKEN_WRITE") or os.environ.get("HF_TOKEN") or ""
    if not t:
        sys.exit("no HF_TOKEN_WRITE in the environment: start in a login shell")
    return t


def stage() -> str:
    r = urllib.request.Request(f"https://huggingface.co/api/spaces/{SPACE}", headers={"Authorization": f"Bearer {token()}"})
    d = json.load(urllib.request.urlopen(r, timeout=20))["runtime"]
    return d["stage"] + (f" {d.get('errorMessage', '')[:200]}" if "ERROR" in d["stage"] else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frame")
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args()
    for _ in range(60):
        s = stage()
        if s == "RUNNING" or "ERROR" in s:
            break
        time.sleep(15)
    print("Space:", s, flush=True)
    if s != "RUNNING":
        sys.exit(1)
    from gradio_client import Client, handle_file
    c = Client(SPACE, token=token(), verbose=False)
    times = {m: [] for m in MODELS}
    for rnd in range(a.rounds):
        for m in MODELS:
            t0 = time.time()
            try:
                r = c.predict(handle_file(a.frame), m, PROMPTS, 0.1, api_name="/detect")
            except Exception as e:  # noqa: BLE001 -- report and go on with the next model
                print(f"{m:11} error {type(e).__name__}: {str(e)[:160]}", flush=True)
                continue
            rt = time.time() - t0
            if rnd:
                times[m].append((rt, r["ms"]))
            print(f"{m:11} round trip {rt:5.2f} s, GPU {r['ms']:7.1f} ms, "
                  f"{[(b[0][:22], b[5]) for b in r['boxes'][:4]]}", flush=True)
    print("\nmedian after the first round:")
    for m, v in times.items():
        if v:
            print(f"  {m:11} round trip {statistics.median(x[0] for x in v):.2f} s, "
                  f"GPU {statistics.median(x[1] for x in v):.0f} ms")


if __name__ == "__main__":
    main()
