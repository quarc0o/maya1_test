# Pinned CUDA 12.4 + PyTorch base. This deliberately matches FastMaya's tested
# A100 / CUDA-12 environment. Do NOT swap in a CUDA-13 / Blackwell (sm_120) base
# image, or you reintroduce the nvrtc / FlashInfer / "no kernel image" failures.
FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/runpod-volume/hf \
    HF_HUB_ENABLE_HF_TRANSFER=1

# git for the pip-from-github install; ffmpeg/libsndfile for audio I/O.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# FastMaya pulls in lmdeploy + the SNAC/AudioSR stack via its pyproject.
# runpod = serverless SDK; soundfile = WAV encoding; hf_transfer = faster pulls.
RUN pip install --no-cache-dir \
        runpod \
        soundfile \
        hf_transfer \
        "git+https://github.com/ysharma3501/FastMaya.git"

WORKDIR /app
COPY handler.py /app/handler.py
COPY test_input.json /app/test_input.json

CMD ["python", "-u", "handler.py"]
