"""Video2Learn API — upload → transcribe → AI questions → H5P export."""

from __future__ import annotations

import json
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import jobs
from .h5p import build_h5p
from .models import JobStatus, QuestionsPayload
from .transcribe import warmup_model

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.restore_all_on_startup()
    warmup_model()
    yield


app = FastAPI(title="Video2Learn", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/videos", status_code=201)
async def upload_video(
    file: UploadFile,
    title: str = Form(...),
    language: str = Form("auto"),
):
    title = title.strip()
    if not title:
        raise HTTPException(400, "title is required")
    if not (file.filename or "").lower().endswith(".mp4"):
        raise HTTPException(400, "only .mp4 files are supported (H.264/AAC)")

    job = jobs.create_job(title=title, language=language or "auto")
    try:
        with open(job.video_path, "wb") as out:
            shutil.copyfileobj(file.file, out)
        jobs.finalize_upload(job)
    except ValueError as e:
        shutil.rmtree(job.dir, ignore_errors=True)
        with jobs._lock:
            jobs.JOBS.pop(job.id, None)
        raise HTTPException(400, str(e)) from e
    except Exception:
        shutil.rmtree(job.dir, ignore_errors=True)
        with jobs._lock:
            jobs.JOBS.pop(job.id, None)
        raise

    return {"id": job.id}


def _get_job_or_404(job_id: str) -> jobs.Job:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "video not found")
    return job


def _status(job: jobs.Job) -> JobStatus:
    segments = 0
    if job.transcript_path.exists():
        try:
            segments = len(json.loads(job.transcript_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            segments = 0
    questions = 0
    if job.questions_path.exists():
        try:
            questions = len(json.loads(job.questions_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            questions = 0
    return JobStatus(
        id=job.id,
        stage=job.stage,
        error=job.error,
        title=job.title,
        language=job.language,
        duration=float(job.meta.get("duration", 0)),
        width=int(job.meta.get("width", 0)),
        height=int(job.meta.get("height", 0)),
        segments=segments,
        question_count=questions,
    )


@app.get("/api/videos/{job_id}")
def video_status(job_id: str) -> JobStatus:
    return _status(_get_job_or_404(job_id))


@app.get("/api/videos/{job_id}/media")
def video_media(job_id: str):
    job = _get_job_or_404(job_id)
    if not job.video_path.exists():
        raise HTTPException(404, "video file missing")
    return FileResponse(job.video_path, media_type="video/mp4", filename=None)


@app.get("/api/videos/{job_id}/transcript")
def video_transcript(job_id: str):
    job = _get_job_or_404(job_id)
    return {"segments": jobs.load_transcript(job)}


@app.get("/api/videos/{job_id}/questions")
def get_questions(job_id: str):
    job = _get_job_or_404(job_id)
    return {"questions": jobs.load_questions(job)}


@app.put("/api/videos/{job_id}/questions")
def put_questions(job_id: str, payload: QuestionsPayload):
    job = _get_job_or_404(job_id)
    if job.stage != "ready" and not job.questions_path.exists():
        raise HTTPException(409, "questions are not ready yet")
    # validate ids unique
    seen: set[str] = set()
    for q in payload.questions:
        if q.id in seen:
            raise HTTPException(400, f"duplicate question id {q.id!r}")
        seen.add(q.id)
    jobs.save_questions(job, [q.model_dump() for q in payload.questions])
    return {"ok": True, "count": len(payload.questions)}


@app.post("/api/videos/{job_id}/regenerate")
def regenerate(job_id: str):
    job = _get_job_or_404(job_id)
    if job.stage in ("upload", "transcribe", "generate"):
        raise HTTPException(409, "pipeline already running")
    if job.transcript_path.exists():
        jobs.start_generation(job)
    elif job.stage == "error":
        # failed before transcription finished: restart the whole pipeline
        jobs.start_pipeline(job)
    else:
        raise HTTPException(409, "transcript not ready yet")
    return {"ok": True}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:60] or "interactive-video"


@app.get("/api/videos/{job_id}/export")
def export_h5p(job_id: str):
    job = _get_job_or_404(job_id)
    questions = jobs.load_questions(job)
    if not questions:
        raise HTTPException(409, "no questions to export yet")
    try:
        out = build_h5p(
            video_path=job.video_path,
            questions=questions,
            title=job.title,
            language=job.language if job.language != "auto" else "en",
            out_path=job.h5p_path,
            video_meta=job.meta,
        )
    except (OSError, ValueError) as e:
        raise HTTPException(500, f"export failed: {e}") from e
    return FileResponse(
        out,
        media_type="application/zip",
        filename=f"{_slugify(job.title)}.h5p",
    )


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
