"""Audio extraction (ffmpeg) + speech-to-text (faster-whisper, CPU)."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import Any

WHISPER_MODEL = os.environ.get("VIDEO2LEARN_WHISPER_MODEL", "base")

_model = None
_model_lock = threading.Lock()


def extract_audio(video_path: Path, wav_path: Path) -> Path:
    """Extract 16 kHz mono WAV audio for transcription."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "wav", str(wav_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)
    return wav_path


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        return _model


def transcribe_audio(wav_path: Path, language: str | None = None) -> list[dict[str, Any]]:
    """Transcribe WAV -> [{start, end, text}] segments (seconds)."""
    model = _get_model()
    segments, _info = model.transcribe(
        str(wav_path),
        language=language if language and language != "auto" else None,
        vad_filter=True,
    )
    out: list[dict[str, Any]] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        out.append({"start": round(float(seg.start), 2), "end": round(float(seg.end), 2), "text": text})
    return out


def warmup_model() -> None:
    """Pre-download the Whisper model so the first job isn't slow."""
    def _warm():
        try:
            _get_model()
        except Exception as e:  # noqa: BLE001 - warmup must never crash the app
            print(f"[warmup] whisper model download failed: {e}")

    threading.Thread(target=_warm, daemon=True).start()
