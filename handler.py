"""
RunPod serverless handler for Maya1 TTS via FastMaya (LMDeploy engine).

Request:
    {"input": {"text": "...", "voice": "..."}}

Response:
    {
      "audio_base64": "<base64 WAV>",
      "sample_rate": 48000,
      "audio_seconds": 4.18,
      "synth_seconds": 0.91,
      "rtf": 0.218          # synth_seconds / audio_seconds; want < 1
    }

The engine loads ONCE at module import (cold start) and is reused across
warm invocations, so only the first request on a fresh worker pays load time.
"""

import os
import io
import time
import base64
import traceback

import soundfile as sf
import runpod

from Maya1.tts_engine import TTSEngine


import os, subprocess
print("HF_HOME =", os.environ.get("HF_HOME"))
print(subprocess.run(["df", "-h"], capture_output=True, text=True).stdout)

# FastMaya upsamples Maya1's native 24 kHz to 48 kHz via its AudioSR stage.
SAMPLE_RATE = 48_000

# Tunables (override via endpoint env vars).
MEMORY_UTIL = float(os.environ.get("MAYA_MEMORY_UTIL", "0.8"))  # frac of VRAM
TP = int(os.environ.get("MAYA_TP", "1"))                        # tensor parallel / #GPUs

# ---- Cold start: load model once -----------------------------------------
print(f"[cold-start] Loading FastMaya TTSEngine (memory_util={MEMORY_UTIL}, tp={TP}) ...")
_t0 = time.time()
engine = TTSEngine(memory_util=MEMORY_UTIL, tp=TP)
print(f"[cold-start] Engine ready in {time.time() - _t0:.1f}s")


def handler(event):
    try:
        data = event.get("input") or {}
        text = data.get("text")
        voice = data.get("voice")

        if not text or not voice:
            return {"error": "Both 'text' and 'voice' are required in input."}

        t0 = time.time()
        audio = engine.generate(text, voice)   # 1-D float numpy @ 48 kHz
        synth_s = time.time() - t0

        # Encode to WAV in-memory, then base64 for JSON transport.
        buf = io.BytesIO()
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
        buf.seek(0)
        audio_b64 = base64.b64encode(buf.read()).decode("utf-8")

        audio_s = len(audio) / SAMPLE_RATE
        return {
            "audio_base64": audio_b64,
            "sample_rate": SAMPLE_RATE,
            "audio_seconds": round(audio_s, 3),
            "synth_seconds": round(synth_s, 3),
            "rtf": round(synth_s / audio_s, 3) if audio_s > 0 else None,
        }

    except Exception as e:
        # Surface the trace so failures are debuggable from the test client.
        return {"error": str(e), "trace": traceback.format_exc()}


runpod.serverless.start({"handler": handler})
