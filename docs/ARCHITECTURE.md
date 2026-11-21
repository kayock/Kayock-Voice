# Architecture

```
                    ┌─────────────────────────────┐
  Browser / UI      │  GET /  (index.html)         │
  Companion apps    │  GET /health  GET /voices    │
  Father Fox        │  POST /speak  → audio/wav    │
                    └──────────────┬──────────────┘
                                   │ :8766 HTTPS
                    ┌──────────────▼──────────────┐
                    │  Kayock Voice (FastAPI)     │
                    │  server.py  v0.3.0          │
                    └──────┬──────────┬───────────┘
           Kokoro ONNX     │          │     Piper subprocess
           (54 voices)     │          │     (optional Trek pack)
                           │          │
                    ┌──────▼──────────▼───────────┐
                    │  Special voices → RVC CLI   │
                    │  (chunked Kokoro carrier +  │
                    │   infer.cli conversion)     │
                    └─────────────────────────────┘

  Chrome Read Aloud / OpenAI TTS clients
                    │ :8768 HTTP
                    ▼
         openai-speech-adapter (adapter.py)
           POST /v1/audio/speech → upstream /speak
           WAV → MP3/opus/aac/flac via ffmpeg
```

## Engines

1. **Kokoro** — default path. Loads `kokoro-v1.0.onnx` + `voices-v1.0.bin` once at import. Language selected from voice-id prefix (`af_`/`am_` → `en-us`, `bf_`/`bm_` → `en-gb`, …) with optional `lang` override.
2. **Piper** — if `voice` or `profile` is `data`, `picard`, or `federation_computer`, synthesis uses `piper-tts` in a separate venv (subprocess + lock).
3. **RVC** — if the voice/profile maps to `special-voices.json`, Kokoro synthesizes a carrier (`am_adam` by default), then RVC converts in word/character chunks under a process-wide lock.

## Process layout (production Portable)

| Unit | Port | Role |
|------|------|------|
| `kayock-voice.service` | `0.0.0.0:8766` TLS | Core TTS |
| `kayock-openai-speech-adapter.service` (user) | `0.0.0.0:8768` HTTP | OpenAI-compatible front door |
| `father-fox-voice.service` | `:8765` | Separate hub; client of `/speak` |

Hard-coded install root in `server.py`: `/opt/kayock-voice/{special-voices,rvc,piper}`.
Adapter upstream URLs are environment-driven (`KAYOCK_SPEAK_URL`, etc.).
