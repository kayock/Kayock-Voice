# Preparation notes (2026-11-20)

Packaged on Ubuntu Station from a **read-only** inspection of Ubuntu Portable
(LAN host; address omitted). Live units were not modified, restarted, or reconfigured.

## Byte-identical to Portable

| File | SHA256 |
|------|--------|
| `server/server.py` | `57cbe8c088237b53a9306a3dbb0692e07d2ae7877228d9d0d0cf009a17e9f4a7` |
| `server/pyproject.toml` | `c5a8be008d9ee282329c12150050d05aa45ffe8c00702a83b8a0344062fc9418` |
| `server/uv.lock` | `132d1ca51bb9637ddf1eaa60bfa646c6f6d3573001c4112c0c1f7734fac4731b` |

## Intentionally sanitized in this tree only

| File | Change |
|------|--------|
| `server/index.html` | Removed personal `eric` RVC fallback label/option |
| `openai-speech-adapter/adapter.py` | Placeholder host in root URL; removed personal `eric` aliases/priority row |
| Example configs / voice list | Relative or layout paths; no personal `eric` RVC entry |
| `READ_ALOUD_CONFIG.md` | Host placeholders; personal voice rows removed |

## Not verified during packaging

- End-to-end `POST /speak` or RVC synthesis (avoided GPU load on live Portable)
- Piper GPL combined-distribution legal review for a specific release artifact
- Rights to redistribute any character-likeness Piper/RVC **models** (models excluded)
- Existence of an **Aurora Companion** client codebase (none found)
