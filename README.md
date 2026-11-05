# Video2Learn

AI-powered interactive learning content generator: upload an educational MP4 → transcribe → AI generates timestamped questions → teacher reviews/edits → export a **Moodle-compatible H5P Interactive Video** (`.h5p`).

## Requirements

- Python 3.12+, FFmpeg
- [opencode](https://opencode.ai) CLI (used headlessly for question generation)
- A browser; Moodle with H5P support for the final import

## Setup

```bash
cd backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Run the server

```bash
cd backend
source venv/bin/activate   # activate the virtualenv first (do not execute ./venv/bin/activate)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or start it detached (keeps running after you close the terminal):

```bash
cd backend
setsid nohup venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/video2learn.log 2>&1 < /dev/null &
```

Stop a detached server with:

```bash
pkill -f "[u]vicorn app.main"
```

Open http://127.0.0.1:8000

First run downloads the Whisper `base` model (~150 MB) in the background.
Override with `VIDEO2LEARN_WHISPER_MODEL=small` for better accuracy (slower).

## Usage

1. **Upload** an MP4 (H.264/AAC), enter a title and language.
2. **Wait** while the pipeline extracts audio, transcribes (faster-whisper, local CPU), and asks opencode to generate timestamped questions.
3. **Review** on the timeline: edit questions/answers/explanations/timestamps, add or delete questions, preview timing against the video.
4. **Download** the `.h5p` and upload it into Moodle as an **H5P activity** (or Content Bank).

## Architecture

```
frontend/            vanilla HTML/JS/CSS (no build step)
backend/app/
  main.py            FastAPI routes
  jobs.py            in-process pipeline jobs (per-video folders)
  transcribe.py      ffmpeg → faster-whisper
  generate.py        opencode CLI subprocess → validated JSON questions
  h5p.py             .h5p (ZIP) package builder
  media.py           ffprobe validation
  models.py          pydantic schemas
backend/h5p_refs/    official H5P semantics (schema source of truth)
data/videos/<id>/    source.mp4, transcript.json, questions.json, output.h5p
```

Pipeline stages: `upload → transcribe → generate → ready` (or `error`, retryable).

## H5P package details

- Format: `h5p.json` + `content/content.json` + `content/<video>.mp4`
- Libraries (matched to H5P Hub bundles): `H5P.InteractiveVideo 1.27`, `H5P.MultiChoice 1.16`, `H5P.TrueFalse 1.8`
- Each question becomes an IV interaction with `pause: true` (video stops, dialog opens)
- Moodle downloads the libraries from the H5P Hub on first import
- Built and verified against the official semantics; validated by real Moodle 5.2.2 imports

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/videos` | upload `file`, `title`, `language` → `{id}` |
| GET | `/api/videos/{id}` | job status |
| GET | `/api/videos/{id}/media` | stream MP4 (Range supported) |
| GET | `/api/videos/{id}/transcript` | transcript segments |
| GET/PUT | `/api/videos/{id}/questions` | read / replace questions |
| POST | `/api/videos/{id}/regenerate` | re-run AI generation |
| GET | `/api/videos/{id}/export` | download `.h5p` |

## Notes / limits (v1)

- MP4 (H.264 video + AAC audio) only
- Single-user local tool — no auth, no database (filesystem + in-process jobs)
- Question counts scale with duration (~1 per 25 s MC, ~1 per 60 s T/F, min gap 15 s)
- `av` is pinned to 14.2.0 (faster-whisper 1.2.1 passes `metadata_errors`, removed in av 15+)
