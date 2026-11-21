# Example configuration

| File | Purpose |
|------|---------|
| `voice-config.example.json` | Named profiles (Kokoro / Piper / RVC keys). Personal voices omitted. |
| `special-voices.example.json` | RVC voice table with **relative** path placeholders. |
| `special-voices.portable-layout.json` | Same table with absolute `/opt/kayock-voice/...` paths matching `server.py`. |
| `piper-models/*.onnx.json` | Piper metadata only (no `.onnx` weights). |

Production `server.py` loads:

- `voice-config.json` from the Kokoro working directory
- `/opt/kayock-voice/special-voices/special-voices.json` (absolute path)

Use the portable-layout special-voices file (or edit paths) when deploying to
that layout. Only enable RVC/Piper entries for models you install and are
allowed to use.
