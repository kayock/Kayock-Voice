# Installation

This package ships **source and example configs only**. Model weights, RVC
runtime, virtualenvs, and TLS certificates are not included.

The production layout expected by `server.py` is:

```text
/opt/kayock-voice/
  kokoro/                 # server.py, index.html, voice-config.json, ONNX models, .venv
  special-voices/         # special-voices.json
  piper/                  # .venv + models/*.onnx
  rvc/                    # .venv + runtime/ (RVC-WebUI clone)
  rvc-models/             # optional .pth / .index per voice
  openai-speech-adapter/  # adapter.py
```

## 1. Prerequisites

- Python 3.12+
- `ffmpeg` on `PATH` (adapter format conversion)
- Optional NVIDIA CUDA stack for RVC (production used Torch `2.7.1+cu118`)
- Outbound access to download Kokoro ONNX assets

## 2. Core Kayock Voice (Kokoro)

```bash
sudo mkdir -p /opt/kayock-voice
sudo chown "$USER:$USER" /opt/kayock-voice
cp -a server /opt/kayock-voice/kokoro
cd /opt/kayock-voice/kokoro

# Dependencies (uv or pip)
uv sync   # uses pyproject.toml / uv.lock
# or: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Download Apache-2.0 Kokoro v1.0 ONNX assets into this directory:
#   https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
#   kokoro-v1.0.onnx
#   voices-v1.0.bin

cp ../config/examples/voice-config.example.json ./voice-config.json
# Adjust as needed
```

Copy example special-voices with absolute paths matching this layout:

```bash
mkdir -p /opt/kayock-voice/special-voices
cp config/examples/special-voices.portable-layout.json \
  /opt/kayock-voice/special-voices/special-voices.json
# Only keep RVC entries for models you actually install and have rights to use.
```

Generate TLS material for production HTTPS (self-signed is what Portable used;
browsers need a click-through, Chrome extensions will not):

```bash
# Example only — replace with your own cert process
openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
  -keyout /opt/kayock-voice/kokoro/kayock-voice.key \
  -out /opt/kayock-voice/kokoro/kayock-voice.crt \
  -subj "/CN=kayock-voice"
```

Install systemd unit from `deploy/systemd/kayock-voice.service` and optional
drop-in `kayock-voice.rvc-memory-safe.conf` →
`/etc/systemd/system/kayock-voice.service.d/rvc-memory-safe.conf`.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kayock-voice.service
curl -sk https://127.0.0.1:8766/health
```

## 3. Optional Piper

```bash
python3.12 -m venv /opt/kayock-voice/piper/.venv
/opt/kayock-voice/piper/.venv/bin/pip install 'piper-tts==1.7.0'
mkdir -p /opt/kayock-voice/piper/models
# Place ONNX + JSON pairs expected by server.py PIPER_MODELS paths.
# Metadata examples (no weights) are in config/examples/piper-models/.
```

Piper is **GPL-3.0-or-later**. See `THIRD_PARTY_NOTICES.md`.

## 4. Optional RVC

```bash
git clone https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI.git \
  /opt/kayock-voice/rvc/runtime
# Create /opt/kayock-voice/rvc/.venv per upstream CUDA/CPU requirements
# Place user-owned .pth/.index under /opt/kayock-voice/rvc-models/...
```

Production sets `RVC_CUDA_GRAPH=0` via the systemd drop-in to reduce VRAM pressure
when other GPU workloads (e.g. Lemonade) share the card.

## 5. OpenAI speech adapter

```bash
cp -a openai-speech-adapter /opt/kayock-voice/
# Reuses the Kokoro venv’s fastapi/uvicorn:
mkdir -p ~/.config/systemd/user
cp deploy/systemd/kayock-openai-speech-adapter.user.service \
  ~/.config/systemd/user/kayock-openai-speech-adapter.service
systemctl --user daemon-reload
systemctl --user enable --now kayock-openai-speech-adapter.service
curl -s http://127.0.0.1:8768/health
```

Chrome Read Aloud setup: see `openai-speech-adapter/READ_ALOUD_CONFIG.md`.

## Environment knobs (server)

| Variable | Default | Purpose |
|----------|---------|---------|
| `KAYOCK_RVC_CHUNK_MAX_WORDS` | 34 | RVC chunking |
| `KAYOCK_RVC_CHUNK_MAX_CHARS` | 240 | RVC chunking |
| `KAYOCK_RVC_CHUNK_TIMEOUT_SECONDS` | 300 | Per-chunk timeout |
| `KAYOCK_RVC_JOIN_SILENCE_MS` | 55 | Silence between chunks |
| `RVC_CUDA_GRAPH` | unset | Set `0` for memory-safe RVC |

## Adapter environment

| Variable | Default |
|----------|---------|
| `KAYOCK_SPEAK_URL` | `https://127.0.0.1:8766/speak` |
| `KAYOCK_VOICES_URL` | `https://127.0.0.1:8766/voices` |
| `KAYOCK_HEALTH_URL` | `https://127.0.0.1:8766/health` |
| `KAYOCK_SPEAK_TIMEOUT_SECONDS` | `600` |
| `FFMPEG_BIN` | `ffmpeg` |
