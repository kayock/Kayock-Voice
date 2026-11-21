# Kayock Voice

**Local-first speech synthesis built for real-world AI projects.**

[![License: MIT](https://img.shields.io/badge/license-MIT-7c3aed.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](docs/INSTALL.md)
[![Package validation](https://github.com/kayock/Kayock-Voice/actions/workflows/package-check.yml/badge.svg)](https://github.com/kayock/Kayock-Voice/actions/workflows/package-check.yml)
![Self-hosted](https://img.shields.io/badge/deployment-self--hosted-2ea043.svg)

**Kokoro ONNX · Optional Piper · Optional RVC · OpenAI-compatible speech API**

---

Local text-to-speech stack with a web UI, multi-engine routing (Kokoro, optional
Piper, optional RVC), and an OpenAI-compatible speech adapter for Chrome Read
Aloud and companion clients.

**Version:** `0.3.0` (FastAPI app title `Kayock Voice`)  
**Source of truth for this package:** Ubuntu Portable production tree
`/opt/kayock-voice` (inspected read-only; live services left untouched).

## Features

- **Kokoro ONNX TTS** — 54 multilingual voice ids, named profiles, speed control
- **Language-aware phonemization** — prefix map (`af_`/`am_` → `en-us`, …) plus optional `lang`, `sentence_pause`, `clause_pause`
- **Optional Piper voices** — e.g. `data`, `picard`, `federation_computer` via subprocess
- **Optional RVC character conversion** — chunked carrier synthesis + `infer.cli`
- **Web UI** — `GET /` serves `index.html` with live `/voices` inventory
- **OpenAI speech adapter** — `POST /v1/audio/speech` on HTTP `:8768` with ffmpeg format conversion
- **CORS open** for LAN/browser clients (no API key in the stock deploy)

## Architecture (short)

```text
Clients ──HTTPS :8766──► Kayock Voice (server.py)
                              ├─ Kokoro ONNX
                              ├─ Piper (optional)
                              └─ RVC (optional)

Clients ──HTTP  :8768──► openai-speech-adapter ──► /speak
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Endpoints

### Kayock Voice (`server.py`, production `:8766` TLS)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| GET | `/health` | Engine status, profiles, special voices |
| GET | `/voices` | Profiles, Kokoro ids, specials |
| POST | `/speak` | Synthesize → `audio/wav` |

`SpeakRequest`: `text`, `profile` (default `father_fox`), optional `voice`,
`speed` (0.5–2.0), `lang`, `sentence_pause`, `clause_pause`.

### OpenAI adapter (`adapter.py`, production `:8768` HTTP)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Adapter + upstream |
| GET | `/v1/models` | OpenAI-style model list |
| GET | `/v1/voices` | Installed voice inventory |
| POST | `/v1/audio/speech` | OpenAI-style TTS (MP3/WAV/…) |

## Repository layout

```text
server/                     # FastAPI TTS app + UI + pyproject/uv.lock
openai-speech-adapter/      # OpenAI-compatible proxy
config/examples/            # Sanitized example configs (no personal voices)
deploy/systemd/             # Unit files + RVC memory-safe drop-in
docs/                       # Architecture, install, integration, exclusions
scripts/verify_package.py   # Offline package checks
THIRD_PARTY_NOTICES.md      # Dependency / model licensing
```

## Installation

See [`docs/INSTALL.md`](docs/INSTALL.md). Model weights, virtualenvs, RVC
runtime, and certificates are **not** shipped — download Kokoro assets from
upstream and supply any Piper/RVC models you have rights to use.

Quick package check (no services touched):

```bash
python3 scripts/verify_package.py
```

## Integration

- **Father Fox** — production client of `POST /speak` (separate repo/service).
- **Chrome Read Aloud** — use the adapter; see `openai-speech-adapter/READ_ALOUD_CONFIG.md`.
- **Aurora Companion** — no Aurora Companion client was present on the inspected
  system; recommended wiring is documented in [`docs/INTEGRATION.md`](docs/INTEGRATION.md).

## Licensing

- Kayock Voice application code: MIT (`LICENSE`). Upstream sources had no
  embedded copyright headers; this LICENSE covers the Kayock-authored files
  published here.
- Third-party libraries and models: `THIRD_PARTY_NOTICES.md`.
- **Not redistributed:** ONNX/Piper/RVC weights, personal voice models,
  recordings, TLS keys, caches. See `docs/EXCLUSIONS.md`.

Character-named Piper/RVC examples document the production schema only. Do not
redistribute trademarked character likeness models unless you have the rights.

## Verified on packaging day (read-only)

Against the production Portable installation (read-only, without restarting units):

| Check | Result |
|-------|--------|
| `kayock-voice.service` | active (uvicorn `server:app` `:8766` TLS) |
| `kayock-openai-speech-adapter` (user) | active (`adapter:app` `:8768`) |
| `GET https://127.0.0.1:8766/health` | `engine=kokoro+rvc`, 54 Kokoro voices, 15 profiles |
| `GET http://127.0.0.1:8768/health` | adapter ok + upstream ok |
| Source SHA256 `server.py` | `57cbe8c0…` (matches Portable) |
| Source SHA256 `adapter.py` | `85dbf773…` (matches Portable) |

Full synthesis load tests were **not** re-run during packaging to avoid GPU
contention with live workloads; prior Portable verification notes are retained
in the adapter Read Aloud doc.
