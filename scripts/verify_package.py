#!/usr/bin/env python3
"""Offline checks for the Kayock-Voice publication tree.

Does not contact live services, start processes, or load model weights.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    ".gitignore",
    "server/server.py",
    "server/index.html",
    "server/pyproject.toml",
    "server/requirements.txt",
    "openai-speech-adapter/adapter.py",
    "openai-speech-adapter/requirements.txt",
    "config/examples/voice-config.example.json",
    "config/examples/special-voices.example.json",
    "config/examples/special-voices.portable-layout.json",
    "deploy/systemd/kayock-voice.service",
    "deploy/systemd/kayock-openai-speech-adapter.user.service",
    "docs/ARCHITECTURE.md",
    "docs/INSTALL.md",
    "docs/INTEGRATION.md",
    "docs/EXCLUSIONS.md",
]

FORBIDDEN_SUFFIXES = (
    ".onnx",
    ".bin",
    ".pth",
    ".pt",
    ".index",
    ".wav",
    ".mp3",
    ".key",
    ".crt",
    ".pem",
)

FORBIDDEN_NAMES = {
    "kokoro-v1.0.onnx",
    "voices-v1.0.bin",
    "kayock-voice.key",
    "kayock-voice.crt",
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    if missing:
        fail(f"missing required files: {missing}")

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            # allow piper *.onnx.json metadata
            if path.suffix == ".json" and path.name.endswith(".onnx.json"):
                continue
            if path.suffix.lower() == ".json":
                continue
            fail(f"forbidden artifact present: {path.relative_to(ROOT)}")

    for py in [
        ROOT / "server" / "server.py",
        ROOT / "openai-speech-adapter" / "adapter.py",
        ROOT / "scripts" / "verify_package.py",
    ]:
        ast.parse(py.read_text(encoding="utf-8"), filename=str(py))

    vc = json.loads((ROOT / "config/examples/voice-config.example.json").read_text())
    sv = json.loads((ROOT / "config/examples/special-voices.example.json").read_text())
    if "eric" in vc or "eric" in sv.get("voices", {}):
        fail("personal eric RVC entry must not appear in example configs")

    ral = json.loads(
        (ROOT / "openai-speech-adapter/read-aloud-voice-list.json").read_text()
    )
    if any(item.get("voice") == "eric" for item in ral):
        fail("personal eric RVC id must not appear in read-aloud voice list")

    # Stock Kokoro id am_eric is fine if present.
    print("OK: package structure, syntax, and sanitization checks passed")
    print(f"ROOT={ROOT}")


if __name__ == "__main__":
    main()
