"""Video probing via ffprobe."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def probe_video(path: Path) -> dict[str, Any]:
    """Return {width, height, mime, duration, format} for an MP4 file.

    Raises ValueError if the file is not a readable MP4 with video+audio.
    """
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "stream=codec_type,codec_name,width,height:format=format_name,duration",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, check=True, timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise ValueError(f"unreadable video file: {e}") from e

    data = json.loads(out.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})

    if video is None:
        raise ValueError("file has no video stream (MP4 with H.264 video required)")
    if audio is None:
        raise ValueError("file has no audio stream (speech-to-text needs audio)")
    if video.get("codec_name") != "h264":
        raise ValueError(f"video codec {video.get('codec_name')} not supported — re-encode to H.264 (MP4)")

    fmt_name = fmt.get("format_name", "")
    if "mp4" not in fmt_name:
        raise ValueError(f"container '{fmt_name}' not supported — MP4 required")

    try:
        duration = float(fmt.get("duration", 0))
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise ValueError("could not determine video duration")

    return {
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "mime": "video/mp4",
        "duration": duration,
        "format": fmt_name,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
    }
