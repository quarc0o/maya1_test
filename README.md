# FastMaya RunPod Serverless Worker

Wraps [FastMaya](https://github.com/ysharma3501/FastMaya) (Maya1 TTS on the
LMDeploy engine, with 24→48 kHz upsampling) as a RunPod serverless endpoint.
Send `{text, voice}`, get back a 48 kHz WAV (base64) plus the server-side RTF.

## Files
- `handler.py` — serverless handler; loads the engine once at cold start.
- `Dockerfile` — pinned CUDA 12.4 image (see the warning below).
- `test_input.json` — local test payload (auto-read by `python handler.py`).
- `call_endpoint.py` — client that calls the deployed endpoint and saves audio.

## ⚠️ The one rule that matters
Deploy on a **CUDA-12.x image with an A100, A10, or L40S** GPU — NOT a
CUDA-13 / Blackwell card (e.g. RTX PRO 4000 Blackwell). FastMaya/LMDeploy has
compiled CUDA kernels; on bleeding-edge Blackwell+CUDA-13 you hit the same
`nvrtc` / "no kernel image for sm_120" failures as the raw vLLM script.
FastMaya was tested on A100/CUDA-12 — match that and it just works.

## 1. Build & push the image
```bash
docker build -t YOUR_DOCKERHUB_USER/fastmaya-worker:latest .
docker push YOUR_DOCKERHUB_USER/fastmaya-worker:latest
```
(Build on an x86_64 machine, not your M4 — the image is CUDA/linux-amd64.
Use a cloud builder or a RunPod Pod if you don't have an x86 box.)

## 2. Create a network volume (weight cache)
In RunPod → Storage → create a ~30 GB network volume. The Dockerfile points
`HF_HOME` at `/runpod-volume/hf`, so the ~6 GB of weights download once on the
first cold start and persist — every later cold worker mounts the cache instead
of re-pulling from HuggingFace.

## 3. Create the serverless endpoint
RunPod → Serverless → New Endpoint:
- Container image: `YOUR_DOCKERHUB_USER/fastmaya-worker:latest`
- GPU: **A100 / L40S / A10** (24 GB+ is plenty; FastMaya runs in 8 GB but give it room)
- Attach the network volume from step 2 (mounts at `/runpod-volume`)
- Optional env: `MAYA_MEMORY_UTIL=0.8`, `MAYA_TP=1`
- Set max workers + idle timeout per your traffic (start small)

## 4. Test it
```bash
export RUNPOD_ENDPOINT_ID=<your endpoint id>
export RUNPOD_API_KEY=<your runpod api key>
pip install requests
python call_endpoint.py
```
You'll get `reply_*.wav` files plus printed RTF and roundtrip. The first call
on a cold endpoint will be slow (cold start + first-time weight download);
subsequent warm calls show the real synth latency.

## Notes / gotchas
- **First cold start is slow twice over**: container pull + 6 GB weight download.
  After the volume is warmed, only the container-pull cold start remains.
- **RTF here is single-request.** FastMaya's headline 50× comes from batching;
  this handler does one request at a time. For your read-aloud chunk pattern
  that's the realistic number anyway.
- **No native streaming yet.** FastMaya returns a complete WAV per call —
  drops straight into your current Ream file-per-chunk transport, but does not
  give Maya1's intra-chunk streaming latency advantage (still on FastMaya's
  to-do list).
- **If `lmdeploy` complains about the torch version** at build/run, align it to
  what the installed lmdeploy wheel expects (pin `torch==` in the Dockerfile to
  match). This is the most likely build-time snag; everything else is standard.
