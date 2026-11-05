"""H5P Interactive Video package builder.

Builds `.h5p` files (ZIP) compatible with Moodle's H5P activity:

    output.h5p
    ├── h5p.json
    └── content/
        ├── content.json
        └── <video file>

Library versions are matched to the bundles served by the H5P Hub
(verified via api.h5p.org/v1/content-types/...):
  H5P.InteractiveVideo 1.27, H5P.MultiChoice 1.16, H5P.TrueFalse 1.8
"""

from __future__ import annotations

import copy
import json
import zipfile
from pathlib import Path
from typing import Any

REFS_DIR = Path(__file__).resolve().parents[1] / "h5p_refs"

IV_LIB = {"machineName": "H5P.InteractiveVideo", "majorVersion": 1, "minorVersion": 27}
MC_LIB = {"machineName": "H5P.MultiChoice", "majorVersion": 1, "minorVersion": 16}
TF_LIB = {"machineName": "H5P.TrueFalse", "majorVersion": 1, "minorVersion": 8}

MC_LIBRARY_STRING = "H5P.MultiChoice 1.16"
TF_LIBRARY_STRING = "H5P.TrueFalse 1.8"


def _load_semantics(name: str) -> list[dict[str, Any]]:
    path = REFS_DIR / f"{name}.semantics.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _group(semantics: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for field in semantics:
        if field.get("name") == name:
            return field
    raise KeyError(f"group {name!r} not found in semantics")


def apply_defaults(fields: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """Fill missing params from semantics defaults (mirrors editor exports).

    H5P's runtime does not apply semantics defaults, so content.json must be
    complete. Groups and lists are created even without defaults because player
    code accesses them unguarded (e.g. `options.video.textTracks.videoTrack`).
    """
    if not isinstance(params, dict):
        params = {}
    for field in fields:
        name = field.get("name")
        if not name:
            continue
        ftype = field.get("type")
        if ftype == "group":
            sub = params.get(name)
            if not isinstance(sub, dict):
                sub = {}
                params[name] = sub
            apply_defaults(field.get("fields", []), sub)
        elif ftype == "list":
            items = params.get(name)
            if not isinstance(items, list):
                items = []
                params[name] = items
            item_sem = field.get("field")
            if isinstance(item_sem, dict):
                item_fields = item_sem.get("fields", [])
                for item in items:
                    if isinstance(item, dict):
                        apply_defaults(item_fields, item)
        elif "default" in field:
            if params.get(name) is None:
                params[name] = copy.deepcopy(field["default"])
        elif ftype == "text":
            # editor exports empty strings for untouched text fields
            if params.get(name) is None:
                params[name] = ""
        elif ftype == "boolean":
            if params.get(name) is None:
                params[name] = False
    return params


def _mc_params(question: dict[str, Any]) -> dict[str, Any]:
    answers = []
    for i, choice in enumerate(question["choices"]):
        answers.append(
            {
                "text": choice,
                "correct": i == question["correct"],
                "tipsAndFeedback": {"tip": "", "chosenFeedback": "", "notChosenFeedback": ""},
            }
        )
    raw = {"question": question["question"], "answers": answers}
    return apply_defaults(_load_semantics("multichoice"), raw)


def _tf_params(question: dict[str, Any]) -> dict[str, Any]:
    raw = {
        "question": question["question"],
        "correct": "true" if question["correct"] == 0 else "false",
    }
    return apply_defaults(_load_semantics("truefalse"), raw)


def _interaction(question: dict[str, Any], sub_content_id: int, item_fields: list[dict[str, Any]]) -> dict[str, Any]:
    start = float(question["time"])
    end = start + float(question.get("duration", 15))

    if question["type"] == "tf":
        params = _tf_params(question)
        library = TF_LIBRARY_STRING
    else:
        params = _mc_params(question)
        library = MC_LIBRARY_STRING

    raw = {
        "duration": {"from": start, "to": end},
        "pause": True,
        "label": "Question",
        "x": 5,
        "y": 10,
        "width": 40,
        "height": 30,
        "libraryTitle": "Question",
        "action": {
            "library": library,
            "params": params,
            "subContentId": sub_content_id,
        },
    }
    item = apply_defaults(item_fields, raw)
    # goto omitted: isGotoClickable() guards undefined type -> no goto UI
    item.pop("goto", None)
    return item


def build_content_json(
    video_path: Path,
    video_meta: dict[str, Any],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    iv_sem = _load_semantics("interactive-video")
    iv_group = _group(iv_sem, "interactiveVideo")

    assets_group = [f for f in iv_group["fields"] if f["name"] == "assets"][0]
    interactions_field = [f for f in assets_group["fields"] if f["name"] == "interactions"][0]
    item_fields = interactions_field["field"]["fields"]

    file_entry = {
        "path": video_path.name,
        "mime": video_meta.get("mime", "video/mp4"),
        "width": video_meta.get("width", 1280),
        "height": video_meta.get("height", 720),
        "copyright": {"license": "U"},
    }

    raw_iv = {
        "video": {"files": [file_entry]},
        "assets": {
            "interactions": [
                _interaction(q, i, item_fields)
                for i, q in enumerate(sorted(questions, key=lambda q: q["time"]))
            ],
            "bookmarks": [],
            "endscreens": [],
        },
        # summary omitted on purpose: hasMainSummary() guards its absence
    }
    interactive_video = apply_defaults(iv_group["fields"], raw_iv)
    # keep summary absent: hasMainSummary() guards undefined, and a stub
    # summary would only add dead weight
    interactive_video.pop("summary", None)
    # goto omitted (re-added by apply_defaults): isGotoClickable() guards
    # undefined type, so a bare goto would be dead weight too
    for it in interactive_video["assets"]["interactions"]:
        it.pop("goto", None)
    override = apply_defaults(_group(iv_sem, "override").get("fields", []), {})
    l10n = apply_defaults(_group(iv_sem, "l10n").get("fields", []), {})

    return {
        "interactiveVideo": interactive_video,
        "override": override,
        "l10n": l10n,
    }


def build_h5p(
    video_path: Path,
    questions: list[dict[str, Any]],
    title: str,
    language: str,
    out_path: Path,
    video_meta: dict[str, Any] | None = None,
) -> Path:
    video_meta = video_meta or {}
    h5p_json = {
        "title": title,
        "language": language,
        "mainLibrary": "H5P.InteractiveVideo",
        "embedTypes": ["iframe"],
        "license": "U",
        "preloadedDependencies": [IV_LIB, MC_LIB, TF_LIB],
    }
    content = build_content_json(video_path, video_meta, questions)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("h5p.json", json.dumps(h5p_json, ensure_ascii=False, indent=2))
        zf.writestr("content/content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.write(video_path, f"content/{video_path.name}")
    return out_path
