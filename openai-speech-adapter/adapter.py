#!/usr/bin/env python3
"""
OpenAI-compatible speech adapter for Kayock Voice.

Exposes:
  GET  /v1/models
  GET  /v1/voices
  POST /v1/audio/speech

Proxies synthesis to the existing Kayock Voice service (POST /speak)
without modifying that pipeline. Converts audio formats with ffmpeg
when the client requests a non-WAV container (Read Aloud uses mp3).
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import tempfile
import urllib.error
import urllib.request
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field


KAYOCK_SPEAK_URL = os.getenv(
    "KAYOCK_SPEAK_URL",
    "https://127.0.0.1:8766/speak",
)
KAYOCK_VOICES_URL = os.getenv(
    "KAYOCK_VOICES_URL",
    "https://127.0.0.1:8766/voices",
)
KAYOCK_HEALTH_URL = os.getenv(
    "KAYOCK_HEALTH_URL",
    "https://127.0.0.1:8766/health",
)
SPEAK_TIMEOUT_SECONDS = float(
    os.getenv("KAYOCK_SPEAK_TIMEOUT_SECONDS", "600")
)
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

# Formats OpenAI documents; we support what ffmpeg can convert from WAV.
SUPPORTED_FORMATS = {
    "mp3": ("audio/mpeg", ["-codec:a", "libmp3lame", "-qscale:a", "2"]),
    "opus": ("audio/opus", ["-codec:a", "libopus", "-b:a", "64k"]),
    "aac": ("audio/aac", ["-codec:a", "aac", "-b:a", "128k"]),
    "flac": ("audio/flac", ["-codec:a", "flac"]),
    "wav": ("audio/wav", None),
    "pcm": ("application/octet-stream", None),
}

# Prefix language map mirrors Kayock Voice / Kokoro id conventions.
KOKORO_LANG_BY_PREFIX = {
    "a": "en-US",
    "b": "en-GB",
    "e": "es-ES",
    "f": "fr-FR",
    "h": "hi-IN",
    "i": "it-IT",
    "j": "ja-JP",
    "p": "pt-BR",
    "z": "zh-CN",
}

PIPER_VOICES = {
    "picard",
    "data",
    "federation_computer",
}

# Display-friendly aliases that still map to real installed IDs.
VOICE_ALIASES = {
    "jean_luc_picard": "picard",
    "jean-luc-picard": "picard",
    "captain_picard": "picard",
    "vader": "darth_vader",
    "darthvader": "darth_vader",
    "optimus": "optimus_prime",
    "rdj": "iron_man",
    "ironman": "iron_man",
}


app = FastAPI(
    title="Kayock OpenAI Speech Adapter",
    version="1.0.0",
    description=(
        "Lightweight OpenAI-compatible front door for Kayock Voice. "
        "Does not replace Father Fox or Kayock Voice."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SpeechRequest(BaseModel):
    model: Optional[str] = Field(default="tts-1")
    input: str
    voice: str
    response_format: Optional[str] = Field(default="mp3")
    speed: Optional[float] = Field(default=1.0)


def _ssl_context() -> ssl.SSLContext:
    # Local loopback to Kayock Voice uses the same self-signed cert
    # Father Fox already trusts via an unverified context.
    return ssl._create_unverified_context()


def _http_json(url: str, timeout: float = 30.0) -> Any:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=_ssl_context(),
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Upstream Kayock Voice error ({exc.code}): {detail}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Kayock Voice: {exc}",
        ) from exc


def _post_speak(payload: dict) -> tuple[bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        KAYOCK_SPEAK_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=SPEAK_TIMEOUT_SECONDS,
            context=_ssl_context(),
        ) as response:
            content_type = response.headers.get(
                "Content-Type",
                "audio/wav",
            )
            return response.read(), content_type
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict) and "detail" in parsed:
                detail = parsed["detail"]
        except Exception:
            pass
        raise HTTPException(
            status_code=exc.code if exc.code < 500 else 502,
            detail=detail,
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Kayock Voice synthesis failed: {exc}",
        ) from exc


def _normalize_voice(voice: str) -> str:
    key = voice.strip().replace(" ", "_")
    lowered = key.lower()
    if lowered in VOICE_ALIASES:
        return VOICE_ALIASES[lowered]
    return lowered


def _lang_for_voice(voice_id: str) -> str:
    if voice_id in PIPER_VOICES:
        return "en-US"
    if "_" in voice_id:
        prefix = voice_id.split("_", 1)[0]
        # Kokoro ids are like af_heart / bm_daniel — first letter of prefix.
        if prefix and prefix[0] in KOKORO_LANG_BY_PREFIX:
            # Two-letter prefixes: af/am/bf/bm/...
            if len(prefix) >= 1 and prefix[0] in KOKORO_LANG_BY_PREFIX:
                return KOKORO_LANG_BY_PREFIX[prefix[0]]
    return "en-US"


def _fetch_registry() -> dict:
    return _http_json(KAYOCK_VOICES_URL)


def _known_voice_ids(registry: dict) -> set[str]:
    ids: set[str] = set()
    ids.update(registry.get("kokoro") or [])
    ids.update((registry.get("special") or {}).keys())
    ids.update((registry.get("profiles") or {}).keys())
    ids.update(PIPER_VOICES)
    return ids


def _resolve_speak_payload(
    voice: str,
    text: str,
    speed: Optional[float],
    registry: dict,
) -> dict:
    voice_id = _normalize_voice(voice)
    known = _known_voice_ids(registry)
    specials = set((registry.get("special") or {}).keys())
    profiles = registry.get("profiles") or {}
    kokoro = set(registry.get("kokoro") or [])

    if voice_id not in known and voice_id not in VOICE_ALIASES.values():
        # After alias normalization, still unknown.
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown voice '{voice}'. "
                "Use GET /v1/voices for installed identifiers."
            ),
        )

    payload: dict[str, Any] = {"text": text}

    if voice_id in specials or voice_id in PIPER_VOICES or voice_id in kokoro:
        payload["voice"] = voice_id
    elif voice_id in profiles:
        # Profile name (e.g. father_fox) — keep existing profile path.
        payload["profile"] = voice_id
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown voice '{voice}'.",
        )

    if speed is not None:
        if not (0.25 <= float(speed) <= 4.0):
            raise HTTPException(
                status_code=400,
                detail="speed must be between 0.25 and 4.0",
            )
        # Kayock Voice / Piper reject outside 0.5–2.0.
        if not (0.5 <= float(speed) <= 2.0):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Kayock Voice engines support speed 0.5–2.0 only; "
                    f"requested {speed}."
                ),
            )
        payload["speed"] = float(speed)
    elif voice_id in specials:
        # Preserve established RVC carrier speed when client omits speed.
        payload["speed"] = 0.92

    return payload


def _convert_audio(wav_bytes: bytes, response_format: str) -> tuple[bytes, str]:
    fmt = (response_format or "mp3").lower().strip()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported response_format '{response_format}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}."
            ),
        )

    content_type, ffmpeg_args = SUPPORTED_FORMATS[fmt]

    if fmt == "wav":
        return wav_bytes, content_type

    if fmt == "pcm":
        # Strip WAV header: use ffmpeg to emit s16le raw PCM.
        ffmpeg_args = ["-f", "s16le", "-acodec", "pcm_s16le"]

    with tempfile.TemporaryDirectory(prefix="kayock-oai-") as tmp:
        src = os.path.join(tmp, "in.wav")
        dst = os.path.join(tmp, f"out.{fmt if fmt != 'pcm' else 'pcm'}")
        with open(src, "wb") as handle:
            handle.write(wav_bytes)

        cmd = [
            FFMPEG_BIN,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
        ]
        if ffmpeg_args:
            cmd.extend(ffmpeg_args)
        cmd.append(dst)

        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=500,
                detail="ffmpeg is not installed; cannot convert audio format.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status_code=500,
                detail="Audio format conversion timed out.",
            ) from exc

        if completed.returncode != 0 or not os.path.exists(dst):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"ffmpeg could not produce '{fmt}': "
                    f"{(completed.stderr or completed.stdout or '').strip()}"
                ),
            )

        with open(dst, "rb") as handle:
            return handle.read(), content_type


def _openai_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": message,
                "type": "invalid_request_error" if status_code < 500 else "server_error",
                "code": status_code,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
    return _openai_error(exc.status_code, message)


@app.get("/health")
def health():
    upstream = None
    try:
        upstream = _http_json(KAYOCK_HEALTH_URL, timeout=10.0)
    except HTTPException as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "adapter": "ok",
                "kayock_voice": "unreachable",
                "detail": exc.detail,
            },
        )
    return {
        "status": "ok",
        "adapter": "ok",
        "kayock_voice": upstream,
        "speak_url": KAYOCK_SPEAK_URL,
    }


@app.get("/v1/models")
def list_models():
    """Read Aloud validates custom OpenAI endpoints with GET /v1/models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "tts-1",
                "object": "model",
                "owned_by": "kayock-voice",
            },
            {
                "id": "tts-1-hd",
                "object": "model",
                "owned_by": "kayock-voice",
            },
            {
                "id": "kokoro",
                "object": "model",
                "owned_by": "kayock-voice",
            },
        ],
    }


@app.get("/v1/voices")
def list_voices():
    """Actual installed voices from the live Kayock Voice registry."""
    registry = _fetch_registry()
    profiles = registry.get("profiles") or {}
    specials = registry.get("special") or {}
    kokoro = registry.get("kokoro") or []

    voices: list[dict] = []
    seen: set[str] = set()

    def add(voice_id: str, *, engine: str, name: str, langs: list[str]):
        if voice_id in seen:
            return
        seen.add(voice_id)
        voices.append(
            {
                "voice": voice_id,
                "name": name,
                "engine": engine,
                "langs": langs,
                "lang": langs[0],
                "model": "tts-1",
            }
        )

    # Priority custom / character voices first.
    priority = [
        ("picard", "piper", "Captain Picard"),
        ("data", "piper", "Data"),
        ("federation_computer", "piper", "Federation Computer"),
        ("darth_vader", "rvc", "Darth Vader"),
        ("batman", "rvc", "Batman"),
        ("optimus_prime", "rvc", "Optimus Prime"),
        ("iron_man", "rvc", "Iron Man"),
    ]
    for voice_id, engine, label in priority:
        if voice_id in specials or voice_id in profiles or voice_id in PIPER_VOICES:
            add(voice_id, engine=engine, name=label, langs=["en-US"])

    for key, meta in profiles.items():
        if key in seen:
            continue
        engine = "rvc" if meta.get("special") else (
            "piper" if key in PIPER_VOICES else "kokoro"
        )
        add(
            key,
            engine=engine,
            name=str(meta.get("name") or key),
            langs=[_lang_for_voice(str(meta.get("voice") or key))],
        )

    for voice_id in sorted(kokoro):
        add(
            voice_id,
            engine="kokoro",
            name=voice_id,
            langs=[_lang_for_voice(voice_id)],
        )

    return {"object": "list", "data": voices}


@app.post("/v1/audio/speech")
def create_speech(req: SpeechRequest):
    text = (req.input or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="input text is required")

    registry = _fetch_registry()
    payload = _resolve_speak_payload(
        voice=req.voice,
        text=text,
        speed=req.speed,
        registry=registry,
    )

    wav_bytes, _upstream_type = _post_speak(payload)
    if not wav_bytes:
        raise HTTPException(status_code=502, detail="Upstream returned empty audio")

    audio, content_type = _convert_audio(
        wav_bytes,
        req.response_format or "mp3",
    )
    return Response(content=audio, media_type=content_type)


@app.get("/")
def root():
    return {
        "service": "kayock-openai-speech-adapter",
        "version": "1.0.0",
        "endpoints": [
            "GET /health",
            "GET /v1/models",
            "GET /v1/voices",
            "POST /v1/audio/speech",
        ],
        "read_aloud_api_url": "http://<host>:8768/v1",
        "upstream": KAYOCK_SPEAK_URL,
    }
