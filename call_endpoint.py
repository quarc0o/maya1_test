#!/usr/bin/env python3
"""
Call the deployed FastMaya RunPod serverless endpoint and save the audio.

Setup:
    export RUNPOD_ENDPOINT_ID=xxxxxxxx
    export RUNPOD_API_KEY=xxxxxxxx
    pip install requests

Run:
    python call_endpoint.py
"""

import os
import sys
import time
import base64
import requests

ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID")
API_KEY = os.environ.get("RUNPOD_API_KEY")

if not ENDPOINT_ID or not API_KEY:
    sys.exit("Set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY environment variables.")

# /runsync blocks until the worker returns (fine for testing). For production
# bursty traffic you'd use /run + poll /status, but runsync is simplest here.
URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"

# A few cases worth comparing — vary length and emotion.
CASES = [
    {
        "name": "neutral_short",
        "text": "The river was calm under the morning light.",
        "voice": "Realistic male voice in the 30s with an American accent. Normal pitch, warm timbre, conversational pacing.",
    },
    {
        "name": "emotional",
        "text": "Welcome back to another episode of our podcast! <laugh_harder> Today we are diving into something fascinating.",
        "voice": "Female, in her 30s with an American accent and is an event host, energetic, clear diction.",
    },
]


def call(case):
    payload = {"input": {"text": case["text"], "voice": case["voice"]}}
    t0 = time.time()
    resp = requests.post(
        URL, json=payload,
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=600,
    )
    resp.raise_for_status()
    roundtrip = time.time() - t0

    body = resp.json()
    out = body.get("output", {})

    if not out or "error" in out:
        print(f"[{case['name']}] worker error: {out.get('error') if out else body}")
        if out.get("trace"):
            print(out["trace"])
        return

    fname = f"reply_{case['name']}.wav"
    with open(fname, "wb") as f:
        f.write(base64.b64decode(out["audio_base64"]))

    print(f"[{case['name']}] saved {fname}")
    print(f"    audio={out['audio_seconds']}s  "
          f"server_synth={out['synth_seconds']}s  RTF={out['rtf']}")
    print(f"    full roundtrip (incl queue/cold-start)={roundtrip:.1f}s")


if __name__ == "__main__":
    for c in CASES:
        call(c)
