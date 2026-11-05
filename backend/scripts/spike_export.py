"""Phase 1 spike: build a minimal 1-MC + 1-TF Interactive Video package."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.h5p import build_h5p  # noqa: E402

VIDEO = ROOT / "fastapi.mp4"
OUT = ROOT / "data" / "spike.h5p"


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,width,height:format=format_name,duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    stream = data["streams"][0]
    fmt = data["format"]
    return {
        "width": stream["width"],
        "height": stream["height"],
        "mime": "video/mp4",
        "duration": float(fmt["duration"]),
        "format": fmt["format_name"],
    }


def main() -> None:
    meta = probe(VIDEO)
    print(f"probe: {meta}")

    questions = [
        {
            "id": "q1",
            "type": "mc",
            "question": "What is FastAPI?",
            "choices": [
                "A modern Python web framework",
                "A relational database",
                "An operating system",
            ],
            "correct": 0,
            "explanation": "FastAPI is a high-performance Python web framework for building APIs.",
            "time": 20,
            "duration": 15,
        },
        {
            "id": "q2",
            "type": "tf",
            "question": "FastAPI supports asynchronous request handlers.",
            "choices": ["True", "False"],
            "correct": 0,
            "explanation": "FastAPI is built on Starlette and supports async/await handlers.",
            "time": 60,
            "duration": 15,
        },
    ]

    out = build_h5p(
        video_path=VIDEO,
        questions=questions,
        title="Video2Learn Spike Test",
        language="en",
        out_path=OUT,
        video_meta=meta,
    )
    print(f"wrote {out} ({out.stat().st_size} bytes)")

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        print("zip entries:", names)
        content = json.loads(zf.read("content/content.json"))
        h5p = json.loads(zf.read("h5p.json"))
        interactions = content["interactiveVideo"]["assets"]["interactions"]
        print(f"interactions: {len(interactions)}")
        for it in interactions:
            print(
                f"  [{it['action']['library']}] from={it['duration']['from']} "
                f"to={it['duration']['to']} pause={it['pause']} "
                f"question={it['action']['params'].get('question', '?')!r}"
            )
        print("h5p.json deps:", h5p["preloadedDependencies"])
        print("l10n keys:", len(content["l10n"]), "| override keys:", len(content["override"]))
        assert "content/fastapi.mp4" in names
        assert content["interactiveVideo"]["video"]["files"][0]["path"] == "fastapi.mp4"
        assert "textTracks" in content["interactiveVideo"]["video"]
        assert "summary" not in content["interactiveVideo"]
        print("SPIKE OK")


if __name__ == "__main__":
    main()
