"""Question generation by invoking the opencode CLI headlessly.

The opencode agent reads the timestamped transcript and returns a strict
JSON object with quiz questions. Output is parsed from the JSON event
stream, validated, normalized, and retried on failure.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

GENERATE_TIMEOUT_S = 300
MAX_ATTEMPTS = 3
MIN_GAP_S = 15.0
DEFAULT_DURATION_S = 15.0


def desired_counts(duration: float) -> tuple[int, int]:
    """(mc, tf) question counts scaled to video length."""
    mc = max(3, min(8, math.ceil(duration / 25)))
    tf = max(1, min(4, round(duration / 60)))
    return mc, tf


def build_prompt(title: str, language: str, duration: float, transcript: list[dict[str, Any]]) -> str:
    mc_n, tf_n = desired_counts(duration)
    lang_line = (
        "Write the questions in English."
        if language in ("", "auto", "en")
        else f"Write the questions in the language with code '{language}'."
    )
    lines = []
    for seg in transcript:
        m, s = divmod(int(seg["start"]), 60)
        lines.append(f"[{m:02d}:{s:02d}] {seg['text']}")
    transcript_block = "\n".join(lines) if lines else "(transcript unavailable)"

    return f"""You are an instructional designer creating a quiz for an educational video.

VIDEO TITLE: {title}
VIDEO DURATION: {duration:.0f} seconds
{lang_line}

TIMESTAMPED TRANSCRIPT:
{transcript_block}

REQUIREMENTS:
- Produce exactly {mc_n} multiple-choice questions and {tf_n} true/false questions.
- Every question must be answerable from the transcript content.
- Distribute questions across the whole video. The "time" value (seconds from the start) must fall inside the video and respect a minimum gap of {int(MIN_GAP_S)} seconds between consecutive questions.
- Multiple-choice: exactly 4 choices, exactly one correct (index 0-3).
- True/false: use choices ["True", "False"], correct is 0 for True, 1 for False.
- "explanation": 1-2 sentences explaining the correct answer.

OUTPUT: output ONLY a single JSON object with this exact shape, no markdown fences, no commentary:

{{"questions":[
  {{"type":"mc","question":"...","choices":["...","...","...","..."],"correct":0,"explanation":"...","time":12.5}},
  {{"type":"tf","question":"...","choices":["True","False"],"correct":1,"explanation":"...","time":60.0}}
]}}"""


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _run_opencode(prompt: str, cwd: Path) -> str:
    """Run opencode headlessly, return concatenated text parts."""
    result = subprocess.run(
        ["opencode", "run", "--format", "json", "--pure", prompt],
        capture_output=True,
        text=True,
        timeout=GENERATE_TIMEOUT_S,
        cwd=str(cwd),
    )
    if result.returncode != 0:
        raise RuntimeError(f"opencode exited {result.returncode}: {result.stderr[:500]}")

    parts: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            part = event.get("part", {})
            txt = part.get("text")
            if txt:
                parts.append(txt)
    if not parts:
        raise RuntimeError("opencode produced no text output")
    return "".join(parts)


def _normalize(raw: dict[str, Any], duration: float) -> list[dict[str, Any]]:
    """Validate + normalize raw questions; drop invalid ones."""
    items = raw.get("questions")
    if not isinstance(items, list):
        raise ValueError("missing 'questions' array")

    mc_n, tf_n = desired_counts(duration)
    valid: list[dict[str, Any]] = []
    seen_mc = seen_tf = 0

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        qtype = item.get("type")
        question = str(item.get("question") or "").strip()
        explanation = str(item.get("explanation") or "").strip()
        try:
            time = float(item.get("time"))
        except (TypeError, ValueError):
            continue
        if not question or time < 0:
            continue

        if qtype == "tf":
            if seen_tf >= tf_n:
                continue
            correct_raw = item.get("correct")
            if isinstance(correct_raw, str):
                correct = 0 if correct_raw.lower() in ("true", "t", "yes") else 1
            elif isinstance(correct_raw, bool):
                correct = 0 if correct_raw else 1
            else:
                correct = int(correct_raw or 0)
            if correct not in (0, 1):
                correct = 0
            choices = ["True", "False"]
            seen_tf += 1
        elif qtype == "mc":
            if seen_mc >= mc_n:
                continue
            choices = item.get("choices")
            if not isinstance(choices, list) or not (2 <= len(choices) <= 4):
                continue
            choices = [str(c).strip() for c in choices]
            if any(not c for c in choices) or len(set(choices)) != len(choices):
                continue
            try:
                correct = int(item.get("correct"))
            except (TypeError, ValueError):
                continue
            if not 0 <= correct < len(choices):
                continue
            seen_mc += 1
        else:
            continue

        valid.append(
            {
                "id": f"q{i + 1}",
                "type": qtype,
                "question": question,
                "choices": choices,
                "correct": correct,
                "explanation": explanation,
                "time": time,
                "duration": DEFAULT_DURATION_S,
            }
        )

    if not valid:
        raise ValueError("no valid questions in model output")

    # sort by time, enforce min gap, keep inside the video
    valid.sort(key=lambda q: q["time"])
    limit = max(0.0, duration - 5.0)
    spaced: list[dict[str, Any]] = []
    prev = -math.inf
    for q in valid:
        t = max(q["time"], prev + MIN_GAP_S)
        if t > limit:
            continue
        q["time"] = round(t, 2)
        spaced.append(q)
        prev = t

    if not spaced:
        raise ValueError("questions could not be spaced inside the video")
    for i, q in enumerate(spaced):
        q["id"] = f"q{i + 1}"
    return spaced


def generate_questions(
    title: str,
    language: str,
    duration: float,
    transcript: list[dict[str, Any]],
    scratch_dir: Path,
) -> list[dict[str, Any]]:
    """Call opencode to generate questions; returns normalized list."""
    prompt = build_prompt(title, language, duration, transcript)
    last_error = "unknown"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            prompt = (
                build_prompt(title, language, duration, transcript)
                + f"\n\nYour previous attempt was invalid ({last_error}). "
                "Output ONLY the JSON object."
            )
        try:
            text = _run_opencode(prompt, scratch_dir)
        except subprocess.TimeoutExpired:
            last_error = "timeout"
            continue
        except RuntimeError as e:
            last_error = str(e)
            continue

        raw = _extract_json(text)
        if raw is None:
            last_error = "response was not valid JSON"
            continue
        try:
            return _normalize(raw, duration)
        except ValueError as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"question generation failed after {MAX_ATTEMPTS} attempts: {last_error}")
