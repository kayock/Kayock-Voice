import io
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from kokoro_onnx import Kokoro


BASE = Path(__file__).resolve().parent

VOICE_CONFIG = BASE / "voice-config.json"
SPECIAL_CONFIG = Path(
    "/opt/kayock-voice/special-voices/special-voices.json"
)

RVC_PYTHON = Path(
    "/opt/kayock-voice/rvc/.venv/bin/python"
)

RVC_RUNTIME = Path(
    "/opt/kayock-voice/rvc/runtime"
)


kokoro = Kokoro(
    str(BASE / "kokoro-v1.0.onnx"),
    str(BASE / "voices-v1.0.bin"),
)

KOKORO_VOICES = set(kokoro.get_voices())


with VOICE_CONFIG.open() as f:
    PROFILES = json.load(f)


with SPECIAL_CONFIG.open() as f:
    SPECIAL_CONFIG_DATA = json.load(f)


SPECIAL_VOICES = SPECIAL_CONFIG_DATA["voices"]
SPECIAL_BASE = SPECIAL_CONFIG_DATA.get(
    "base",
    {}
)
RVC_DEFAULTS = SPECIAL_CONFIG_DATA.get(
    "conversion_defaults",
    {}
)


RVC_LOCK = threading.Lock()


# KAYOCK_RVC_CHUNKING_V1
#
# Long text may be supplied to /speak. Special RVC voices are converted
# internally in smaller jobs so a comic page or long Father Fox answer
# does not become one enormous RVC subprocess.

RVC_CHUNK_MAX_WORDS = max(
    12,
    int(os.getenv("KAYOCK_RVC_CHUNK_MAX_WORDS", "34")),
)

RVC_CHUNK_MAX_CHARS = max(
    100,
    int(os.getenv("KAYOCK_RVC_CHUNK_MAX_CHARS", "240")),
)

RVC_CHUNK_TIMEOUT_SECONDS = max(
    120,
    int(os.getenv("KAYOCK_RVC_CHUNK_TIMEOUT_SECONDS", "300")),
)

RVC_JOIN_SILENCE_MS = max(
    0,
    int(os.getenv("KAYOCK_RVC_JOIN_SILENCE_MS", "55")),
)


# KAYOCK_LANG_MAP_V1
#
# Codes accepted by the installed espeak backend. zh and fr are not.

SUPPORTED_LANGS = {
    "en-us",
    "en-gb",
    "es",
    "fr-fr",
    "hi",
    "it",
    "ja",
    "pt-br",
    "cmn",
}

_LANG_PREFIXES = (
    ("af_", "en-us"),
    ("am_", "en-us"),
    ("bf_", "en-gb"),
    ("bm_", "en-gb"),
    ("ef_", "es"),
    ("em_", "es"),
    ("ff_", "fr-fr"),
    ("hf_", "hi"),
    ("hm_", "hi"),
    ("if_", "it"),
    ("im_", "it"),
    ("jf_", "ja"),
    ("jm_", "ja"),
    ("pf_", "pt-br"),
    ("pm_", "pt-br"),
    ("zf_", "cmn"),
    ("zm_", "cmn"),
)

# Kokoro's own defaults. Omitted request fields must keep these.
DEFAULT_SENTENCE_PAUSE = 0.25
DEFAULT_CLAUSE_PAUSE = 0.1
MIN_PAUSE_SECONDS = 0.0
MAX_PAUSE_SECONDS = 5.0


def lang_for_kokoro_voice(voice: str) -> str:
    """Language for a Kokoro voice id. Unknown ids stay American English."""

    for prefix, code in _LANG_PREFIXES:
        if voice.startswith(prefix):
            return code

    return "en-us"


def resolve_kokoro_lang(
    voice: str,
    override: Optional[str],
) -> str:
    if override is None or not str(override).strip():
        return lang_for_kokoro_voice(voice)

    code = str(override).strip().lower()

    if code not in SUPPORTED_LANGS:
        supported = ", ".join(sorted(SUPPORTED_LANGS))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported language: {override}. "
                f"Supported: {supported}"
            ),
        )

    return code


def optional_pause(
    name: str,
    value: Optional[float],
) -> Optional[float]:
    if value is None:
        return None

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise HTTPException(
            status_code=400,
            detail=f"{name} must be a number of seconds",
        )

    number = float(value)

    if (
        number < MIN_PAUSE_SECONDS
        or number > MAX_PAUSE_SECONDS
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{name} must be between "
                f"{MIN_PAUSE_SECONDS} and {MAX_PAUSE_SECONDS} seconds"
            ),
        )

    return number


app = FastAPI(
    title="Kayock Voice",
    version="0.3.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SpeakRequest(BaseModel):
    text: str

    # Existing Kayock Voice contract.
    profile: str = "father_fox"

    # Optional direct voice ID.
    # Kokoro examples:
    #   am_adam
    #   af_heart
    #
    # Special examples:
    #   batman
    #   optimus_prime
    #   darth_vader
    voice: Optional[str] = None

    speed: Optional[float] = None

    # Optional. Blank uses the voice-id prefix map.
    lang: Optional[str] = None

    # Kokoro only. Omitted values keep the engine defaults.
    sentence_pause: Optional[float] = None

    clause_pause: Optional[float] = None


def make_kokoro_samples(
    text: str,
    voice: str,
    speed: float,
    lang: Optional[str] = None,
    sentence_pause: Optional[float] = None,
    clause_pause: Optional[float] = None,
):
    if lang is None:
        lang = lang_for_kokoro_voice(voice)

    kwargs = {}

    if sentence_pause is not None:
        kwargs["sentence_pause"] = sentence_pause

    if clause_pause is not None:
        kwargs["clause_pause"] = clause_pause

    return kokoro.create(
        text,
        voice=voice,
        speed=speed,
        lang=lang,
        **kwargs,
    )


def make_wav_bytes(
    samples,
    rate,
):
    audio = io.BytesIO()

    sf.write(
        audio,
        samples,
        rate,
        format="WAV",
    )

    return audio.getvalue()


def _rvc_word_count(value: str):
    return len(
        re.findall(
            r"\S+",
            value or "",
        )
    )


def _rvc_boundary_word(word: str):
    """
    A punctuation hint, not a command.

    Comic OCR can contain wild punctuation, so this is only used
    when choosing a good cut near the size boundary.
    """
    cleaned = word.rstrip(
        "\"'”’)]}"
    )

    return cleaned.endswith(
        (
            ".",
            "!",
            "?",
            ";",
            ":",
            ",",
        )
    )


def _rvc_force_split_unit(unit: str):
    """
    Split an oversized sentence/paragraph without cutting words
    unless a single OCR token itself is absurdly long.
    """

    words = unit.split()

    if not words:
        return []

    pieces = []
    current = []

    def current_text():
        return " ".join(current)

    for word in words:

        # A pathological OCR token should not defeat the entire page.
        if len(word) > RVC_CHUNK_MAX_CHARS:

            if current:
                pieces.append(current_text())
                current = []

            for pos in range(
                0,
                len(word),
                RVC_CHUNK_MAX_CHARS,
            ):
                part = word[
                    pos:pos + RVC_CHUNK_MAX_CHARS
                ].strip()

                if part:
                    pieces.append(part)

            continue

        candidate_words = current + [word]
        candidate = " ".join(candidate_words)

        over_limit = (
            len(candidate_words) > RVC_CHUNK_MAX_WORDS
            or len(candidate) > RVC_CHUNK_MAX_CHARS
        )

        if not over_limit:
            current.append(word)
            continue

        if not current:
            current = [word]
            continue

        # Prefer punctuation near the END of the filled chunk.
        # Ignore earlier stray OCR punctuation.
        floor = max(
            1,
            int(len(current) * 0.60),
        )

        cut = None

        for idx in range(
            len(current) - 1,
            floor - 1,
            -1,
        ):
            if _rvc_boundary_word(current[idx]):
                cut = idx + 1
                break

        if cut is None:
            pieces.append(current_text())
            current = [word]
        else:
            pieces.append(
                " ".join(current[:cut])
            )

            current = (
                current[cut:]
                + [word]
            )

            # Extremely unusual fallback if leftovers are still huge.
            while (
                len(current) > RVC_CHUNK_MAX_WORDS
                or len(" ".join(current))
                > RVC_CHUNK_MAX_CHARS
            ):
                pieces.append(
                    " ".join(
                        current[:RVC_CHUNK_MAX_WORDS]
                    )
                )
                current = current[
                    RVC_CHUNK_MAX_WORDS:
                ]

    if current:
        pieces.append(current_text())

    return [
        piece.strip()
        for piece in pieces
        if piece.strip()
    ]


def split_rvc_text(text: str):
    """
    Comic-friendly speech chunking.

    Hierarchy:
      1. Newlines / paragraph boundaries are useful hints.
      2. Normal sentence endings are useful hints.
      3. Tiny fragments are merged back together.
      4. Hard size limits win over bad OCR punctuation.
      5. A word boundary is the normal final fallback.
    """

    normalized = (
        (text or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )

    if not normalized:
        return []

    soft_units = []

    # Treat newlines as soft balloon/paragraph boundaries.
    for block in re.split(
        r"\n+",
        normalized,
    ):
        block = re.sub(
            r"[ \t]+",
            " ",
            block,
        ).strip()

        if not block:
            continue

        # Sentence punctuation is only a hint.
        # Tiny pieces created by stray OCR punctuation will be
        # merged by the packing stage below.
        sentences = re.split(
            r"(?<=[.!?])\s+",
            block,
        )

        for sentence in sentences:
            sentence = sentence.strip()

            if sentence:
                soft_units.extend(
                    _rvc_force_split_unit(
                        sentence
                    )
                )

    chunks = []
    current = ""

    for unit in soft_units:

        if not current:
            current = unit
            continue

        candidate = (
            current.rstrip()
            + " "
            + unit.lstrip()
        )

        fits = (
            _rvc_word_count(candidate)
            <= RVC_CHUNK_MAX_WORDS
            and len(candidate)
            <= RVC_CHUNK_MAX_CHARS
        )

        if fits:
            current = candidate
        else:
            chunks.append(
                current.strip()
            )
            current = unit

    if current.strip():
        chunks.append(
            current.strip()
        )

    return chunks


def _run_rvc_audio_chunk(
    chunk_text: str,
    special,
    base_voice: str,
    speed: float,
    temp_dir: Path,
    chunk_number: int,
    chunk_total: int,
):
    """
    Generate one short Kokoro carrier and convert it through RVC.
    """

    samples, rate = make_kokoro_samples(
        chunk_text,
        base_voice,
        speed,
    )

    source = temp_dir / (
        f"source-{chunk_number:04d}.wav"
    )

    output = temp_dir / (
        f"output-{chunk_number:04d}.wav"
    )

    sf.write(
        source,
        samples,
        rate,
        format="WAV",
    )

    cmd = [
        str(RVC_PYTHON),
        "-m",
        "infer.cli",

        "--model",
        special["model"],

        "--input",
        str(source),

        "--output",
        str(output),

        "--speaker-id",
        "0",

        "--pitch",
        str(
            RVC_DEFAULTS.get(
                "pitch",
                0,
            )
        ),

        "--f0-method",
        str(
            RVC_DEFAULTS.get(
                "f0_method",
                "rmvpe",
            )
        ),

        "--index",
        special["index"],

        "--index-rate",
        str(
            special.get(
                "index_rate",
                RVC_DEFAULTS.get(
                    "index_rate",
                    0.75,
                ),
            )
        ),

        "--rms-mix-rate",
        str(
            RVC_DEFAULTS.get(
                "rms_mix_rate",
                1.0,
            )
        ),

        "--protect",
        str(
            RVC_DEFAULTS.get(
                "protect",
                0.33,
            )
        ),

        "--format",
        "wav",

        "--overwrite",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(
        RVC_RUNTIME
    )

    print(
        "[RVC chunk] "
        f"{chunk_number}/{chunk_total} "
        f"chars={len(chunk_text)} "
        f"words={_rvc_word_count(chunk_text)}",
        flush=True,
    )

    result = subprocess.run(
        cmd,
        cwd=str(RVC_RUNTIME),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=RVC_CHUNK_TIMEOUT_SECONDS,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "RVC conversion failed "
            f"on chunk {chunk_number}/{chunk_total}:\n"
            + result.stdout[-4000:]
        )

    if not output.exists():
        raise RuntimeError(
            "RVC reported success but did not create "
            f"chunk {chunk_number}/{chunk_total} output"
        )

    converted, converted_rate = sf.read(
        output,
        dtype="float32",
        always_2d=True,
    )

    if converted.size == 0:
        raise RuntimeError(
            "RVC created an empty audio chunk "
            f"{chunk_number}/{chunk_total}"
        )

    return converted, converted_rate


def run_rvc(
    text: str,
    special_key: str,
    speed: float,
):
    special = SPECIAL_VOICES.get(
        special_key
    )

    if not special:
        raise RuntimeError(
            f"Unknown special voice: {special_key}"
        )

    base_voice = SPECIAL_BASE.get(
        "voice",
        "am_adam",
    )

    chunks = split_rvc_text(
        text
    )

    if not chunks:
        raise RuntimeError(
            "No speakable text remained after RVC chunking"
        )

    print(
        "[RVC long-text] "
        f"voice={special_key} "
        f"input_chars={len(text)} "
        f"chunks={len(chunks)} "
        f"max_words={RVC_CHUNK_MAX_WORDS} "
        f"max_chars={RVC_CHUNK_MAX_CHARS}",
        flush=True,
    )

    converted_parts = []
    output_rate = None
    output_channels = None

    with tempfile.TemporaryDirectory(
        prefix="kayock-rvc-"
    ) as temp_dir:

        temp_dir = Path(
            temp_dir
        )

        # Keep one request together. Another browser/device cannot
        # interleave a different character conversion halfway through
        # a comic page.
        with RVC_LOCK:

            for idx, chunk_text in enumerate(
                chunks,
                start=1,
            ):
                converted, rate = (
                    _run_rvc_audio_chunk(
                        chunk_text,
                        special,
                        base_voice,
                        speed,
                        temp_dir,
                        idx,
                        len(chunks),
                    )
                )

                if output_rate is None:
                    output_rate = rate
                    output_channels = (
                        converted.shape[1]
                    )

                if rate != output_rate:
                    raise RuntimeError(
                        "RVC chunk sample rates did not match"
                    )

                if (
                    converted.shape[1]
                    != output_channels
                ):
                    raise RuntimeError(
                        "RVC chunk channel counts did not match"
                    )

                converted_parts.append(
                    converted
                )

    if not converted_parts:
        raise RuntimeError(
            "RVC produced no converted audio"
        )

    if len(converted_parts) == 1:
        merged = converted_parts[0]

    else:
        joined = []

        pause_frames = int(
            output_rate
            * RVC_JOIN_SILENCE_MS
            / 1000
        )

        pause = np.zeros(
            (
                pause_frames,
                output_channels,
            ),
            dtype=np.float32,
        )

        for idx, part in enumerate(
            converted_parts
        ):
            if idx and pause_frames:
                joined.append(
                    pause
                )

            joined.append(
                part
            )

        merged = np.concatenate(
            joined,
            axis=0,
        )

    # Return mono as a normal 1-D WAV signal.
    if (
        merged.ndim == 2
        and merged.shape[1] == 1
    ):
        merged = merged[:, 0]

    print(
        "[RVC long-text complete] "
        f"voice={special_key} "
        f"chunks={len(chunks)} "
        f"frames={len(merged)} "
        f"rate={output_rate}",
        flush=True,
    )

    return make_wav_bytes(
        merged,
        output_rate,
    )




# KAYOCK_PIPER_TREK_VOICES_V1
#
# Direct lightweight Piper voices.
# These intentionally DO NOT use SPECIAL_RVC_VOICES and therefore
# do not trigger the Ollama -> RVC GPU handoff.

PIPER_PYTHON = Path(
    "/opt/kayock-voice/piper/.venv/bin/python"
)

PIPER_MODELS = {
    "data": {
        "name": "Data",
        "model": Path(
            "/opt/kayock-voice/piper/models/"
            "en_US-data_7024-medium.onnx"
        ),
    },
    "picard": {
        "name": "Jean-Luc Picard",
        "model": Path(
            "/opt/kayock-voice/piper/models/"
            "en_US-picard_7399-medium.onnx"
        ),
    },
    "federation_computer": {
        "name": "Federation Computer",
        "model": Path(
            "/opt/kayock-voice/piper/models/"
            "en_US-fedcomp-medium.onnx"
        ),
    },
}

PIPER_LOCK = threading.Lock()


def run_piper(
    text: str,
    voice_key: str,
    speed: float = 1.0,
):
    voice = PIPER_MODELS.get(
        voice_key
    )

    if not voice:
        raise RuntimeError(
            f"Unknown Piper voice: {voice_key}"
        )

    model = voice["model"]
    config = Path(
        str(model) + ".json"
    )

    if not PIPER_PYTHON.exists():
        raise RuntimeError(
            f"Piper Python missing: {PIPER_PYTHON}"
        )

    if not model.exists():
        raise RuntimeError(
            f"Piper model missing: {model}"
        )

    if not config.exists():
        raise RuntimeError(
            f"Piper config missing: {config}"
        )

    if not 0.5 <= speed <= 2.0:
        raise RuntimeError(
            "Speed must be between 0.5 and 2.0"
        )

    # Piper length scale is inverse to speaking speed.
    # speed=1.0 therefore reproduces the exact defaults
    # used in our successful voice auditions.
    length_scale = 1.0 / speed

    with tempfile.TemporaryDirectory(
        prefix="kayock-piper-"
    ) as temp_dir:

        output = (
            Path(temp_dir)
            / f"{voice_key}.wav"
        )

        cmd = [
            str(PIPER_PYTHON),
            "-m",
            "piper",
            "-m",
            str(model),
            "-c",
            str(config),
            "-f",
            str(output),
            "--length-scale",
            f"{length_scale:.5f}",
        ]

        with PIPER_LOCK:
            result = subprocess.run(
                cmd,
                input=text + "\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
            )

        if result.returncode != 0:
            raise RuntimeError(
                "Piper synthesis failed:\n"
                + result.stdout[-4000:]
            )

        if (
            not output.exists()
            or output.stat().st_size == 0
        ):
            raise RuntimeError(
                "Piper reported success but "
                "created no audio"
            )

        return output.read_bytes()


def resolve_request(
    req: SpeakRequest,
):
    # --------------------------------------------------------
    # Direct voice request from Father Fox or another client.
    # --------------------------------------------------------

    if req.voice:

        if req.voice in SPECIAL_VOICES:

            speed = (
                req.speed
                if req.speed is not None
                else SPECIAL_BASE.get(
                    "speed",
                    0.92
                )
            )

            return {
                "special": req.voice,
                "voice": SPECIAL_BASE.get(
                    "voice",
                    "am_adam"
                ),
                "speed": float(speed),
            }

        if req.voice not in KOKORO_VOICES:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Unknown voice: "
                    f"{req.voice}"
                ),
            )

        speed = (
            req.speed
            if req.speed is not None
            else 1.0
        )

        return {
            "special": None,
            "voice": req.voice,
            "speed": float(speed),
        }

    # --------------------------------------------------------
    # Existing Kayock profile request.
    # --------------------------------------------------------

    profile = PROFILES.get(
        req.profile
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown voice profile: "
                f"{req.profile}"
            ),
        )

    speed = (
        req.speed
        if req.speed is not None
        else profile.get(
            "speed",
            1.0
        )
    )

    return {
        "special": profile.get(
            "rvc_key"
        ),
        "voice": profile.get(
            "voice",
            "am_adam"
        ),
        "speed": float(speed),
    }


@app.get("/")
def home():
    return FileResponse(
        BASE / "index.html"
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "engine": "kokoro+rvc",
        "kokoro_voice_count": len(
            KOKORO_VOICES
        ),
        "profiles": list(
            PROFILES.keys()
        ),
        "special_voices": list(
            SPECIAL_VOICES.keys()
        ),
    }


@app.get("/voices")
def voices():
    profile_data = {}

    for key, value in PROFILES.items():
        profile_data[key] = {
            "name": value.get(
                "display_name",
                value.get(
                    "name",
                    key
                )
            ),
            "voice": value.get(
                "voice"
            ),
            "speed": value.get(
                "speed",
                1.0
            ),
            "special": bool(
                value.get(
                    "rvc_key"
                )
            ),
        }

    return {
        "profiles": profile_data,
        "kokoro": sorted(
            KOKORO_VOICES
        ),
        "special": {
            key: {
                "name": value.get(
                    "display_name",
                    key
                )
            }
            for key, value
            in SPECIAL_VOICES.items()
        },
    }


@app.post("/speak")
def speak(req: SpeakRequest):

    text = req.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text supplied",
        )

    # KAYOCK_PIPER_DIRECT_DISPATCH_V1
    #
    # Support either a direct voice ID or a Piper profile.
    piper_key = None

    if (
        req.voice
        and req.voice in PIPER_MODELS
    ):
        piper_key = req.voice

    elif (
        req.profile
        and req.profile in PIPER_MODELS
    ):
        piper_key = req.profile

    if piper_key:

        speed = (
            req.speed
            if req.speed is not None
            else 1.0
        )

        if not 0.5 <= speed <= 2.0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Speed must be between "
                    "0.5 and 2.0"
                ),
            )

        try:
            audio = run_piper(
                text,
                piper_key,
                speed,
            )

        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail="Piper synthesis timed out",
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )

        return Response(
            content=audio,
            media_type="audio/wav",
        )

    resolved = resolve_request(
        req
    )

    speed = resolved["speed"]

    if not 0.5 <= speed <= 2.0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Speed must be between "
                "0.5 and 2.0"
            ),
        )

    try:
        if resolved["special"]:

            audio = run_rvc(
                text,
                resolved["special"],
                speed,
            )

        else:

            lang = resolve_kokoro_lang(
                resolved["voice"],
                req.lang,
            )

            sentence_pause = optional_pause(
                "sentence_pause",
                req.sentence_pause,
            )

            clause_pause = optional_pause(
                "clause_pause",
                req.clause_pause,
            )

            samples, rate = (
                make_kokoro_samples(
                    text,
                    resolved["voice"],
                    speed,
                    lang,
                    sentence_pause,
                    clause_pause,
                )
            )

            audio = make_wav_bytes(
                samples,
                rate,
            )

    except HTTPException:
        raise

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Voice conversion timed out",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return Response(
        content=audio,
        media_type="audio/wav",
    )
