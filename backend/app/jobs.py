"""In-process job store + pipeline workers.

Each video is a folder under data/videos/<id>/ with:
    source.mp4, audio.wav, transcript.json, questions.json, meta.json, output.h5p
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .generate import generate_questions
from .media import probe_video
from .transcribe import extract_audio, transcribe_audio

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "videos"

_lock = threading.Lock()
JOBS: dict[str, "Job"] = {}

STAGES = ["upload", "transcribe", "generate", "ready"]


@dataclass
class Job:
    id: str
    dir: Path
    title: str = ""
    language: str = "auto"
    stage: str = "upload"
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def video_path(self) -> Path:
        return self.dir / "source.mp4"

    @property
    def transcript_path(self) -> Path:
        return self.dir / "transcript.json"

    @property
    def questions_path(self) -> Path:
        return self.dir / "questions.json"

    @property
    def meta_path(self) -> Path:
        return self.dir / "meta.json"

    @property
    def h5p_path(self) -> Path:
        return self.dir / "output.h5p"


def _save_meta(job: Job) -> None:
    data = {
        "id": job.id,
        "title": job.title,
        "language": job.language,
        "meta": job.meta,
    }
    job.meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_stage(job: Job, stage: str, error: str = "") -> None:
    with _lock:
        job.stage = stage
        job.error = error


def get_job(job_id: str) -> Job | None:
    with _lock:
        job = JOBS.get(job_id)
    if job is None:
        job = _restore_from_disk(job_id)
    return job


def create_job(title: str, language: str) -> Job:
    job_id = uuid.uuid4().hex[:12]
    job_dir = DATA_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job = Job(id=job_id, dir=job_dir, title=title, language=language, stage="upload")
    with _lock:
        JOBS[job_id] = job
    return job


def finalize_upload(job: Job) -> None:
    """Probe the saved source.mp4, persist meta, kick off the pipeline."""
    job.meta = probe_video(job.video_path)
    _save_meta(job)
    start_pipeline(job)


def start_pipeline(job: Job) -> None:
    threading.Thread(target=_run_pipeline, args=(job,), daemon=True).start()


def start_generation(job: Job) -> None:
    set_stage(job, "generate")
    threading.Thread(target=_run_generation, args=(job,), daemon=True).start()


def _run_pipeline(job: Job) -> None:
    try:
        set_stage(job, "transcribe")
        wav = job.dir / "audio.wav"
        if not job.transcript_path.exists():
            extract_audio(job.video_path, wav)
            language = None if job.language in ("", "auto") else job.language
            segments = transcribe_audio(wav, language)
            if not segments:
                raise RuntimeError("no speech detected in the video")
            job.transcript_path.write_text(
                json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        _run_generation(job)
    except Exception as e:  # noqa: BLE001 - any pipeline failure surfaces to UI
        set_stage(job, "error", _friendly(e))


def _run_generation(job: Job) -> None:
    try:
        set_stage(job, "generate")
        transcript = json.loads(job.transcript_path.read_text(encoding="utf-8"))
        duration = float(job.meta.get("duration", 0)) or _duration_from_transcript(transcript)
        questions = generate_questions(
            title=job.title,
            language=job.language,
            duration=duration,
            transcript=transcript,
            scratch_dir=job.dir,
        )
        job.questions_path.write_text(
            json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        set_stage(job, "ready")
    except Exception as e:  # noqa: BLE001
        set_stage(job, "error", _friendly(e))


def _duration_from_transcript(transcript: list[dict[str, Any]]) -> float:
    return max((float(s.get("end", 0)) for s in transcript), default=60.0)


def _friendly(e: Exception) -> str:
    msg = str(e).strip() or e.__class__.__name__
    return msg[:500]


def load_questions(job: Job) -> list[dict[str, Any]]:
    if not job.questions_path.exists():
        return []
    return json.loads(job.questions_path.read_text(encoding="utf-8"))


def save_questions(job: Job, questions: list[dict[str, Any]]) -> None:
    job.questions_path.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_transcript(job: Job) -> list[dict[str, Any]]:
    if not job.transcript_path.exists():
        return []
    return json.loads(job.transcript_path.read_text(encoding="utf-8"))


def _restore_from_disk(job_id: str) -> Job | None:
    job_dir = DATA_DIR / job_id
    meta_file = job_dir / "meta.json"
    if not meta_file.exists():
        return None
    data = json.loads(meta_file.read_text(encoding="utf-8"))
    job = Job(
        id=data.get("id", job_id),
        dir=job_dir,
        title=data.get("title", ""),
        language=data.get("language", "auto"),
        meta=data.get("meta", {}),
    )
    if (job_dir / "source.mp4").exists() is False:
        return None
    if job.questions_path.exists():
        job.stage = "ready"
    elif job.transcript_path.exists():
        # pipeline was interrupted after transcription: resume generation
        with _lock:
            JOBS[job.id] = job
        start_generation(job)
        return job
    else:
        job.stage = "error"
        job.error = "pipeline was interrupted — please re-upload the video"
    with _lock:
        JOBS[job.id] = job
    return job


def restore_all_on_startup() -> None:
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return
    for entry in sorted(DATA_DIR.iterdir()):
        if entry.is_dir() and (entry / "meta.json").exists():
            _restore_from_disk(entry.name)
