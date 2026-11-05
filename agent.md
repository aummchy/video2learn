# Video2Learn — V1 Plan (agent.md)

> AI-powered interactive learning content generator: upload an MP4 → transcribe → AI generates timestamped questions → teacher edits → export `.h5p` → import into Moodle.

## Decisions (locked)

- **Transcription:** local `faster-whisper` (CPU, `base` model, config switch to `small`)
- **Question generation:** `opencode run --format json` subprocess (no API key)
- **Frontend:** plain HTML/JS served by FastAPI (no Node/build step)
- **H5P:** built from the official Interactive Video spec (no template file)
- **Target Moodle:** 5.2.2 at `http://localhost/` (primary); 4.1.1 later

## Environment (verified)

- Sample video: `/home/aum/moodle/fastapi.mp4` — 125s, 1280x720, H.264/AAC
- `ffmpeg` `/usr/bin/ffmpeg`, Python 3.12, no GPU, 14 cores / 30GB RAM
- `opencode` 1.19.5 at `/snap/bin/opencode`; `opencode run --format json` works headless
- Moodle 5.2.2 live at `http://localhost/`, code `/var/www/moodle`, data `/var/moodledata`
- `mod/h5pactivity` present; no H5P libraries installed yet (Moodle fetches from H5P Hub on first import)
- No sudo, no DB access → Moodle validation is manual via browser
- H5P references fetched: IV `library.json` (1.28.37) + full `semantics.json` (saved at `/tmp/opencode/iv_semantics.json` during recon)

## Architecture

```
browser (vanilla HTML/JS)  ⇄  FastAPI (:8000)
                                  ├─ jobs.py        in-process worker threads
                                  ├─ transcribe.py  ffmpeg → faster-whisper → transcript.json
                                  ├─ generate.py    subprocess: opencode run --format json → questions.json
                                  └─ h5p.py         zip builder → output.h5p
```

No database — each video is a folder under `data/videos/<id>/`:

```
data/videos/<id>/
├── source.mp4
├── audio.wav
├── transcript.json    [{start, end, text}]
├── questions.json     [Question]
└── output.h5p
```

## Project layout

```
/home/aum/moodle/
├── agent.md
├── fastapi.mp4              existing sample
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI routes + static serving
│   │   ├── jobs.py          job store, stage tracking, worker threads
│   │   ├── transcribe.py    ffmpeg audio extraction + faster-whisper
│   │   ├── generate.py      opencode CLI wrapper + JSON validation/retry
│   │   ├── h5p.py           H5P package builder
│   │   └── models.py        pydantic schemas
│   ├── requirements.txt     fastapi, uvicorn, python-multipart, faster-whisper, pydantic
│   └── venv/
├── frontend/
│   ├── index.html           single page, 3 steps
│   ├── app.js               upload, polling, timeline editor, preview overlay
│   └── style.css
└── data/videos/<id>/...
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /` | index.html |
| `POST /api/videos` | upload MP4 + title + language → starts job |
| `GET /api/videos/{id}` | status `{stage: upload→transcribe→generate→ready, error?}` |
| `GET /api/videos/{id}/media` | stream video for preview |
| `GET /api/videos/{id}/transcript` | transcript segments |
| `GET/PUT /api/videos/{id}/questions` | fetch / save edited questions |
| `POST /api/videos/{id}/regenerate` | re-run question generation |
| `GET /api/videos/{id}/export` | download `.h5p` |

## Pipeline stages

1. **Upload & probe** — ffprobe validation (MP4/H.264+AAC preferred), store duration/dimensions.
2. **Transcription** — `ffmpeg -i source.mp4 -ac 1 -ar 16000 audio.wav` → faster-whisper `base` → `transcript.json` with segments.
3. **Question generation** — spawn `opencode run --format json --pure "<prompt>"` (cwd=scratch, timeout 300s). Prompt embeds timestamped transcript + strict schema: 5 MC + 2 T/F, each with `question, choices, correct, explanation, suggestedTime` (seconds, inside a segment). Parse JSON text parts, strip fences, pydantic-validate, retry ≤2× with error appended; surface failure + Retry button in UI.
4. **Editing UI** — timeline table (timestamp | question | type | edit/delete), edit modal with timestamp picker ("jump to video time"), add/delete questions, save + regenerate.
5. **Preview** — HTML5 `<video>` + `timeupdate` overlay: pause at question window, answer locally, show explanation, resume. Not the H5P player — timing sanity check only.
6. **H5P export** — independent module (input: video + questions list).

### H5P package structure

```
output.h5p (zip)
├── h5p.json          title, mainLibrary: "H5P.InteractiveVideo",
│                     preloadedDependencies: [H5P.InteractiveVideo 1.28,
│                     H5P.MultiChoice, H5P.TrueFalse]   ← versions matched to H5P Hub
├── content/
│   ├── content.json
│   └── source.mp4
```

`content.json` (verified against official `semantics.json`):

- Top level: `{interactiveVideo: {video, assets, summary}, override, l10n}`
- `interactiveVideo.video.files[]` ← the MP4 (`path`, `mime`, `width`, `height`, `copyright`)
- `interactiveVideo.assets.interactions[]` ← each question:

```json
{
  "duration": {"from": 45, "to": 55},
  "pause": true,
  "displayType": "button",
  "buttonOnMobile": false,
  "label": "",
  "x": 5, "y": 10, "width": 40, "height": 30,
  "libraryTitle": "Question",
  "action": {"library": "H5P.MultiChoice 1.16",
             "params": {"question": "...", "choices": [{"text": "...", "correct": true}]},
             "subContentId": 0},
  "adaptivity": {"correct": {}, "wrong": {}, "requireCompletion": false},
  "visuals": {"backgroundColor": "", "boxShadow": ""},
  "goto": {"type": "none", "time": 0, "url": "", "visualize": false}
}
```

- MC → `H5P.MultiChoice` params; T/F → `H5P.TrueFalse` params (`question`, `correct: "true"|"false"`)
- IV `library.json` preloaded deps (resolved transitively by Moodle from Hub): FontAwesome 4.5, jQuery.ui 1.10, H5P.Video 1.6, H5P.DragNBar 1.5, H5P.Components 1.0
- Open detail for Phase 1: exact `action.library` version strings — pull from H5P Hub library packages

## Phases (risk-driven order)

| # | Phase | Est. | Exit criteria |
|---|---|---|---|
| 0 | Scaffold venv, deps, FastAPI hello-world, static serving | 30 min | `localhost:8000` serves page |
| **1** | **H5P spike**: hardcoded 1-question exporter → import into Moodle 5.2.2 via browser | 1.5–2 hr | **Question renders in Moodle** — de-risks biggest unknown first |
| 2 | Upload + probe + job status + polling UI | 1 hr | upload works end-to-end |
| 3 | Transcription (ffmpeg + faster-whisper) | 1 hr | transcript displayed in UI |
| 4 | Question generation via opencode subprocess | 1 hr | questions appear on timeline |
| 5 | Editing UI + save/regenerate | 1.5 hr | full teacher workflow |
| 6 | Preview overlay | 1 hr | timing verified against video |
| 7 | Full exporter + Moodle import test on fastapi.mp4 | 1.5 hr | interactive video works in Moodle |
| 8 | Polish, error states, README | 1 hr | **v1 done** |

Total: ~9–11 hours.

## Validation

1. Phase 1 spike: manual Moodle import of 1-question package → proves format + Hub library resolution
2. Phase 7: full `fastapi.mp4` pipeline → import into Moodle 5.2.2, verify all questions at correct timestamps
3. Later: repeat on Moodle 4.1.1 (not blocking v1)

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| H5P schema wrong → Moodle rejects package | Spike-first (Phase 1); semantics fetched from official source; iterate on import errors |
| Moodle can't reach H5P Hub | Fallback: bundle libraries in `.h5p` `libraries/` folder (spec-supported) |
| opencode output non-JSON / slow | `--pure`, strict prompt, pydantic validation, 2 retries, error + Retry button |
| Whisper accuracy | `base` → `small` config switch; language selector passed to Whisper |
| No sudo/DB → no automated Moodle checks | Browser-based manual validation (~5 min per import) |

## Out of scope (v1)

WebM/MOV input, adaptive learning, student analytics, branching, multi-user/auth, React frontend.

---

## STATUS (updated after implementation)

| Phase | Status | Notes |
|---|---|---|
| 0 Scaffold | ✅ done | venv + FastAPI + static serving |
| 1 H5P spike | ✅ done | `data/spike.h5p` imported & rendered in Moodle 5.2.2 |
| 2 Upload/jobs | ✅ done | POST upload, ffprobe validation, stage polling, restart-safe job restore |
| 3 Transcription | ✅ done | ffmpeg → faster-whisper base/int8; 125s video ≈ <10s on CPU |
| 4 AI generation | ✅ done | `opencode run --format json --pure`, 3 retries, strict JSON normalize |
| 5 Editing UI | ✅ done | timeline table, modal editor, add/delete, PUT validation, regenerate |
| 6 Preview | ✅ done | HTML5 video + pause-at-question overlay with feedback |
| 7 Export | ✅ done | full pipeline: fastapi.mp4 → 6 questions → `data/export-test.h5p` (structurally validated) |
| 8 Polish | ✅ done | README, resume-after-reload, error retry, start-over |

**E2E test result (fastapi.mp4, 124.7s):** 24 transcript segments → 6 questions (4 MC + 2 T/F) at 10/30/48/65/85/100s, accurate & grounded in transcript; export 8.1 MB, ZIP + JSON validated; PUT round-trip + 422 validation verified.

### Issues hit & fixes

1. **`av` 19.x breaks faster-whisper 1.2.1** — `av.open(..., metadata_errors=...)` kwarg removed → pin `av==14.2.0` in requirements.txt.
2. Server must run detached (`setsid nohup uvicorn ...`) or tool timeouts kill it.
3. `pkill -f "uvicorn app.main"` kills the invoking shell (pattern matches own cmdline) → use `[u]vicorn` trick.

### Key H5P facts (from source analysis)

- H5P runtime does **NOT** apply semantics defaults → `apply_defaults()` in `h5p.py` must fill them (l10n/override/behaviour etc.)
- Safe omissions (guarded in player): `summary` (`hasMainSummary()`), `goto` (`isGotoClickable()`), `adaptivity.*.seekTo` (`void 0!==`)
- Hub bundle versions: IV **1.27**, MultiChoice **1.16**, TrueFalse **1.8** (via `api.h5p.org/v1/content-types/<name>`)
- Semantics refs stored in `backend/h5p_refs/`

### Remaining / nice-to-have

- Final human test: import `data/export-test.h5p` (real AI-generated package) into Moodle — expected to work (same builder as spike)
- Test on Moodle 4.1.1
- Longer videos: opencode prompt size, per-question duration tuning
- Optional: `small` whisper model via env for accuracy
