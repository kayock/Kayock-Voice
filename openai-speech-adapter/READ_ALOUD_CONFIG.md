# Read Aloud → Kayock Voices

Verified against the Portable deployment on 2026-11-05. Replace
`<host>` with your Kayock Voice machine address.

## 1. API URL

```
http://<host>:8768/v1
```

Paste that value into Read Aloud → Options → Enable custom voices → OpenAI → **API URL**.

Do **not** use `https://<host>:8766` or `/speak`. Kayock Voice has no OpenAI
`/v1/audio/speech` route, and a self-signed HTTPS certificate is rejected by
Chrome extensions (no click-through). The adapter is plain HTTP on port **8768**
for that reason.

## 2. API key

```
not-needed
```

No authentication is required by the stock adapter. Use `not-needed` so Read
Aloud’s save/test (`GET /v1/models` with a Bearer header) succeeds.

## 3. Voice List

Paste the contents of `read-aloud-voice-list.json` (stock Kokoro + optional
Piper/RVC ids). Priority custom voices verified via the adapter on Portable:

| Voice ID | Engine | Verified |
|----------|--------|----------|
| `picard` | Piper | yes (MP3) |
| `data` | Piper | listed / installed |
| `federation_computer` | Piper | listed / installed |
| `darth_vader` | RVC | yes (MP3) |
| `batman` | RVC | listed / installed |
| `optimus_prime` | RVC | listed / installed |
| `iron_man` | RVC | listed / installed |
| `am_adam` | Kokoro | yes (MP3) |
| `af_heart` | Kokoro | yes (MP3) |

Minimal paste if you only want the priority set:

```json
[
  {"voice": "picard", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "data", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "federation_computer", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "darth_vader", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "batman", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "optimus_prime", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "iron_man", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "am_adam", "langs": ["en-US"], "model": "tts-1"},
  {"voice": "af_heart", "langs": ["en-US"], "model": "tts-1"}
]
```

After Save, voices appear as **OpenAI &lt;id&gt;** in the Voices dropdown (for example `OpenAI picard`).

## 4. Startup behavior

User systemd unit (no root required):

- Unit: `~/.config/systemd/user/kayock-openai-speech-adapter.service`
- Code: `/opt/kayock-voice/openai-speech-adapter/adapter.py`
- Depends on Kayock Voice at `https://127.0.0.1:8766`

```bash
systemctl --user status kayock-openai-speech-adapter.service
systemctl --user restart kayock-openai-speech-adapter.service
systemctl --user stop kayock-openai-speech-adapter.service
```

A system-level unit file is also provided in `deploy/systemd/`.

## 5. Verification results (Portable, 2026-11-05)

| Check | Result |
|-------|--------|
| `GET http://<host>:8768/health` | ok, upstream kokoro+rvc |
| `GET /v1/models` (Read Aloud save test) | 200 |
| `GET /v1/voices` | 69 installed voices |
| CORS preflight from `chrome-extension://…` | `access-control-allow-origin: *` |
| `POST /v1/audio/speech` → MP3 | 200 |

| Voice | HTTP | Format |
|-------|------|--------|
| `am_adam` (Kokoro) | 200 | audio/mpeg |
| `picard` (Piper) | 200 | audio/mpeg |
| `darth_vader` (RVC) | 200 | audio/mpeg |

| Case | Result |
|------|--------|
| Unknown voice | 404 OpenAI-style `error` object |
| speed `3.5` | 400 (engines support 0.5–2.0 only) |
| `response_format: ogg` | 400 unsupported |

### Known browser notes

- **Why not HTTPS `:8766`?** Self-signed cert. Tabs can click through; Chrome extension `fetch` cannot.
- **Why not Father Fox `/api/talk`?** Requires recorded audio + client ID; not a TTS endpoint.

## Rollback

```bash
systemctl --user disable --now kayock-openai-speech-adapter.service
# Kayock Voice and Father Fox are untouched
```
