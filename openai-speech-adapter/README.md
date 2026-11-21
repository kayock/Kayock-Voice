# Kayock OpenAI Speech Adapter

Lightweight OpenAI-compatible front door for **Kayock Voice** so Chrome
**Read Aloud: A Text to Speech Voice Reader** (and similar clients) can use
local Kokoro, Piper, and RVC voices.

- Does **not** modify Father Fox (`:8765`) or Kayock Voice (`:8766`).
- Listens on **HTTP `0.0.0.0:8768`** by default (Chrome extensions reject
  self-signed HTTPS without a trusted CA).
- Proxies `POST /v1/audio/speech` → Kayock Voice `POST /speak`.
- Converts WAV → MP3 (and other formats) with `ffmpeg`.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Adapter + upstream health |
| GET | `/v1/models` | Read Aloud save/validation |
| GET | `/v1/voices` | Live installed voice inventory |
| POST | `/v1/audio/speech` | OpenAI-style synthesis |

## Install / start

Preferred (user unit; see `../deploy/systemd/`):

```bash
mkdir -p ~/.config/systemd/user
cp ../deploy/systemd/kayock-openai-speech-adapter.user.service \
  ~/.config/systemd/user/kayock-openai-speech-adapter.service
systemctl --user daemon-reload
systemctl --user enable --now kayock-openai-speech-adapter.service
systemctl --user status kayock-openai-speech-adapter.service
```

## Read Aloud configuration

See **`READ_ALOUD_CONFIG.md`** for API URL, key, voice JSON, and test notes.
