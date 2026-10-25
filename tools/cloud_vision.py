#!/usr/bin/env python3
"""EXPERIMENTAL stub: one camera frame to a cloud vision model, with the user's own API key.

What: builds the request that would ask a vision model (OpenAI or Gemini) which sound healing
      instruments it sees in a frame and where, as boxes for the app's protocol:
        [(label, x, y, w, h, confidence), ...]   normalised 0..1
      In v0 it sends NOTHING: build_request() returns the request without its key, and ask()
      returns no boxes. tools/camera_live.py calls it only when the app's Camera page has Cloud AI
      set to On AND a key is in the environment; otherwise it is never imported.
Why:  owner 25.10.2026: ChakraV is the experimental sibling of Chakra, "max auf dem Device onboard AI
      und API key versuchen": on-device AI first, cloud models with your own key for comparison.
Keys: only from the environment (OPENAI_API_KEY or GEMINI_API_KEY; on the Mac filled from the
      keychain), never from a file, an argument or the repository; never printed. On the board a
      key would come only from encrypted NVS (tools/provision.py). The launcher strips every key from
      its children, so in the Ideas launcher this never runs.
Privacy: a cloud call would send a picture of the room to the provider. That is why it is off by
      default, needs a key the user set up, and does not exist yet as a real call.
Usage:  cloud_vision.py --dry-run FRAME.jpg     shows which provider and model it would use and the
                                                request's size, sends nothing
"""
import argparse
import base64
import json
import os
import sys

PROMPT = ("Which sound healing instruments are in this picture (singing bowl, tuning fork, gong, chimes, drum, "
          "others)? Answer as JSON: a list of {label, x, y, w, h, confidence}, box normalised 0..1 from the top left.")
PROVIDERS = {
    "openai": {"env": "OPENAI_API_KEY", "model": "gpt-5-mini", "url": "https://api.openai.com/v1/responses"},
    "gemini": {"env": "GEMINI_API_KEY", "model": "gemini-2.5-flash",
               "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"},
}


def provider() -> str | None:
    """The first provider whose key is in the environment, or None: then nothing may run."""
    for name, p in PROVIDERS.items():
        if os.environ.get(p["env"], "").strip():
            return name
    return None


def build_request(jpeg: bytes, name: str) -> dict:
    """The request as it would go out, without the key (it would be added as a header at send time)."""
    image = base64.b64encode(jpeg).decode()
    p = PROVIDERS[name]
    if name == "openai":
        body = {"model": p["model"], "input": [{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image}"}]}]}
    else:
        body = {"contents": [{"parts": [{"text": PROMPT}, {"inline_data": {"mime_type": "image/jpeg", "data": image}}]}]}
    return {"url": p["url"], "model": p["model"], "body": body}


def ask(jpeg: bytes) -> list:
    """Boxes for one frame. v0: the request is built, nothing is sent, no boxes come back."""
    name = provider()
    if not name:
        return []
    build_request(jpeg, name)
    return []  # v0: no network call (README, "Next")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frame")
    ap.add_argument("--dry-run", action="store_true", help="the only mode in v0")
    a = ap.parse_args()
    name = provider()
    if not name:
        sys.exit("no OPENAI_API_KEY or GEMINI_API_KEY in the environment: Cloud AI stays off")
    with open(a.frame, "rb") as f:
        req = build_request(f.read(), name)
    print(f"would send {len(json.dumps(req['body'])) // 1024} KB to {name} ({req['model']}) at {req['url']}; "
          "v0 sends nothing")


if __name__ == "__main__":
    main()
