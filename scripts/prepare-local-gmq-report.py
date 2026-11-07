"""Prepare a local-only, browser-readable GMQ evidence bundle for LINK."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def add_local_video(source: Path, destination: Path) -> None:
    if destination.exists():
        source_stat = source.stat()
        destination_stat = destination.stat()
        if (source_stat.st_dev, source_stat.st_ino) == (destination_stat.st_dev, destination_stat.st_ino):
            return
        raise FileExistsError(f"Refusing to overwrite existing local demo video: {destination}")
    try:
        os.link(source, destination)
    except OSError as error:
        raise RuntimeError(
            "Could not create an E: drive hard link for the local GMQ video; "
            "the script will not duplicate the 135 MB source file."
        ) from error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--multimodal-dir", type=Path, required=True)
    parser.add_argument("--actions-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "frontend/public/local-demo/gmq",
    )
    args = parser.parse_args()

    video = args.video.resolve(strict=True)
    multimodal = args.multimodal_dir.resolve(strict=True)
    actions_dir = args.actions_dir.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    video_target = output_dir / "gmq.mp4"
    add_local_video(video, video_target)

    transcripts = []
    for row in read_csv(multimodal / "gmq_asr_transcript.csv"):
        transcripts.append({
            "id": row["segment_id"],
            "startMs": int(row["start_ms"]),
            "endMs": int(row["end_ms"]),
            "text": row["text"],
        })

    acoustic = []
    acoustic_counts: Counter[str] = Counter()
    for row in read_csv(multimodal / "gmq_acoustic_cues.csv"):
        label = row["candidate_label"].split("/")[0].strip()
        acoustic_counts[label] += 1
        acoustic.append({
            "startMs": int(row["start_ms"]),
            "endMs": int(row["end_ms"]),
            "label": label,
            "score": number(row.get("candidate_score")),
            "text": row.get("text", ""),
        })

    face_summary = json.loads((multimodal / "gmq_face_expression_summary.json").read_text(encoding="utf-8"))
    face = []
    for row in read_csv(multimodal / "gmq_face_expression_1fps.csv"):
        smile_left = number(row.get("mouthSmileLeft"))
        smile_right = number(row.get("mouthSmileRight"))
        face.append({
            "timeMs": int(row["time_ms"]),
            "status": row["status"],
            "mouthSmile": (smile_left + smile_right) / 2 if smile_left is not None and smile_right is not None else None,
            "browInnerUp": number(row.get("browInnerUp")),
            "jawOpen": number(row.get("jawOpen")),
        })

    action_rows = read_csv(actions_dir / "gmq_机器逐点记录.csv")
    actions = []
    action_counts: Counter[str] = Counter()
    for row in action_rows:
        label = row.get("动作中文", "").strip()
        if not label:
            continue
        time_s = number(row.get("原视频秒"))
        if time_s is None:
            continue
        action_counts[label] += 1
        actions.append({
            "timeMs": round(time_s * 1000),
            "label": label,
            "confidence": number(row.get("模型置信分数")),
        })

    payload = {
        "title": "GMQ 信息科技试讲",
        "durationMs": int(face_summary["duration_ms"]),
        "videoUrl": "/local-demo/gmq/gmq.mp4",
        "transcripts": transcripts,
        "acoustic": acoustic,
        "acousticCounts": dict(acoustic_counts),
        "face": face,
        "faceCoverage": face_summary["observed_ratio"],
        "faceStatusCounts": face_summary["status_counts"],
        "actions": actions,
        "actionCounts": dict(action_counts),
        "recordCounts": {
            "transcripts": len(transcripts),
            "acousticSegments": len(acoustic),
            "faceSamples": len(face),
            "actionSamples": len(action_rows),
        },
    }
    (output_dir / "report.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(output_dir),
        "video_link": str(video_target),
        "video_is_hardlink": os.stat(video).st_ino == os.stat(video_target).st_ino,
        "counts": payload["recordCounts"],
        "actions": payload["actionCounts"],
        "acoustic": payload["acousticCounts"],
        "face_coverage": payload["faceCoverage"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
