# Integration

## Father Fox Voice Hub (verified client)

On Ubuntu Portable, Father Fox (`father-fox-voice.service`, HTTPS `:8765`) posts
JSON to Kayock Voice:

```text
POST https://127.0.0.1:8766/speak
{"text": "...", "voice": "<id>", "speed": 1.0|0.92}
```

- Non-special voices use speed `1.0`.
- Special RVC voices use speed `0.92` and may release shared GPU memory first.
- Father Fox source lives outside this repository (`~/father-fox-hub`); it is a
  **client**, not part of the Kayock Voice package.

## OpenAI-compatible clients (Read Aloud)

Point any OpenAI TTS-compatible client at the adapter:

```text
API base:  http://<host>:8768/v1
API key:   not-needed
POST       /v1/audio/speech
```

Body fields used by the adapter: `model`, `input`, `voice`, `response_format`
(`mp3` recommended), optional `speed` (0.5–2.0).

## Aurora Companion

No source, systemd unit, or API client named **Aurora Companion** was found on
the inspected Portable Kayock Voice install or in related Station lab trees
during packaging (2026-11-20).

For a companion-style app (desktop/browser agent that needs local speech):

1. Prefer the **adapter** OpenAI surface (`:8768`) for HTTP + MP3 compatibility.
2. Or call Kayock Voice directly: `POST /speak` with `text` + `profile` or `voice`.
3. Discover inventory via `GET /voices` or adapter `GET /v1/voices`.
4. Health-check `GET /health` (core) or adapter `GET /health` (includes upstream).

If Aurora Companion is a separate Kayock product with a different integration
contract, wire it using the endpoints above once that client’s repository is
available — nothing was invented here.

## Other observed clients (not packaged)

| Client | How it talks to Voice |
|--------|------------------------|
| Comic Reader | Optional `POST` with `profile=father_fox` to `:8766` |
| Chrome Read Aloud | Adapter `:8768/v1` |
| Stellar Cartography | Optional narration notes exist elsewhere; not a required dependency |

## Sample requests

```bash
# Core WAV
curl -sk https://127.0.0.1:8766/speak \
  -H 'content-type: application/json' \
  -d '{"text":"Hello from Kayock Voice.","profile":"father_fox"}' \
  -o hello.wav

# Adapter MP3
curl -s http://127.0.0.1:8768/v1/audio/speech \
  -H 'content-type: application/json' \
  -d '{"model":"tts-1","input":"Hello from the adapter.","voice":"am_adam","response_format":"mp3"}' \
  -o hello.mp3
```
