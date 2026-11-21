# Exclusions from this package

The following exist on the production Ubuntu Portable install under
`/opt/kayock-voice` (and related paths) but are **intentionally omitted**
from this GitHub-ready tree.

| Excluded | Reason |
|----------|--------|
| `kokoro-v1.0.onnx`, `voices-v1.0.bin` | Large model weights; download from upstream Apache-2.0 release |
| `piper/models/*.onnx` | Large weights; optional; fan/character IP sensitivity |
| `piper/.venv`, `kokoro/.venv`, `rvc/.venv` | Machine-local environments |
| Entire `rvc/runtime` git clone (~GB) | Third-party project; clone upstream |
| `rvc-models/**` (`.pth`, `.index`, zips) | Model weights; character likeness / personal voice |
| Personal RVC voice `eric` (weights + config entries) | Private biometric / personal voice data |
| UI fallback label/option for personal `eric` RVC | Removed from published `index.html` only; live Portable UI unchanged |
| Adapter aliases/priority entry for personal `eric` RVC | Removed from published `adapter.py` only; live Portable adapter unchanged |
| `special-voices/reference/*.wav` | Reference audio clips |
| TLS `kayock-voice.key` / `kayock-voice.crt` | Machine secrets |
| `backups/**` | Historical snapshots, not product source |
| Generated / cached audio, `__pycache__` | Ephemeral |
| Father Fox Hub (`father-fox-hub`, port 8765) | Separate product; integrates as a client |
| Craft STT (`craft_stt_server`, port 8769) | Separate STT stack, not Kayock Voice TTS |

Example configs in `config/examples/` use relative or `/opt/kayock-voice`
layout paths and omit the personal `eric` RVC entry.
