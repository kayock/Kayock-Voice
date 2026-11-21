# Third-party notices

Kayock Voice application code in this repository (FastAPI server, web UI, and
OpenAI speech adapter) is MIT-licensed (see `LICENSE`). It depends on, or
optionally shells out to, the following components. **None of the model
weights listed below are redistributed in this repository.**

## Runtime libraries (Python)

| Component | Role | License (as installed / upstream) |
|-----------|------|-----------------------------------|
| [fastapi](https://github.com/fastapi/fastapi) | HTTP API | MIT |
| [uvicorn](https://github.com/encode/uvicorn) | ASGI server | BSD-3-Clause |
| [pydantic](https://github.com/pydantic/pydantic) | Request models | MIT |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | Kokoro ONNX TTS wrapper | MIT |
| [soundfile](https://github.com/bastibe/python-soundfile) | WAV I/O | BSD-3-Clause |
| [numpy](https://numpy.org/) | Audio buffers | BSD |
| [onnxruntime](https://onnxruntime.ai/) | ONNX inference | MIT |
| [piper-tts](https://github.com/OHF-Voice/piper1-gpl) | Optional Piper engine (separate venv, subprocess) | **GPL-3.0-or-later** |
| [ffmpeg](https://ffmpeg.org/) | Adapter WAV→MP3/etc. | LGPL/GPL (distribution dependent) |

`phonemizer` (GPL) may appear in the Kokoro environment via transitive
dependencies. Review your distribution obligations if you bundle that
environment.

## Models (download separately)

| Artifact | Source | License / notes |
|----------|--------|-----------------|
| `kokoro-v1.0.onnx`, `voices-v1.0.bin` | [kokoro-onnx model-files-v1.0](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0) / [hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Apache-2.0 (model). Some Kokoro training data uses CC BY attribution (see upstream model card). |
| Piper ONNX voices | User-supplied | Depends on each voice pack. **Star Trek–style fan voices are not redistributed here** and may implicate third-party IP. |
| RVC `.pth` / `.index` | User-supplied | Depends on trainer and source audio. Character-likeness models are **not** redistributed here. |

## Optional RVC runtime (clone separately)

Kayock Voice shells out to
[Retrieval-based-Voice-Conversion-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI)
(`python -m infer.cli`) under MIT License (Copyright 2023 liujing04 / 源文雨 / Ftps).
Do **not** vendor that tree into this repo unless you also include its
`LICENSE` and satisfy any nested dependency licenses.

## GPL boundary note

Piper is invoked as an external process from a dedicated virtualenv, not
imported into the Kayock Voice process. Distributors who ship Piper
alongside this software should treat Piper’s GPL terms as applying to the
Piper component and any combined distribution they create.
