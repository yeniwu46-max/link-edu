#!/usr/bin/env python3
"""Render timestamped MM-TBA action predictions over the original video."""

import argparse
import bisect
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2


PALETTE = [
    (255, 164, 66),
    (80, 210, 255),
    (96, 220, 125),
    (205, 120, 255),
    (80, 160, 255),
    (235, 235, 235),
]


def load_events(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        data = data.get("events", [data])
    events = sorted(data, key=lambda item: float(item["time_seconds"]))
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--fps", type=float, required=True)
    args = parser.parse_args()

    events = load_events(args.events)
    times = [float(item["time_seconds"]) for item in events]
    capture = cv2.VideoCapture(args.video)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or args.fps
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(
        args.output, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output video: {args.output}")

    labels = Counter()
    scores = defaultdict(list)
    minute_counts = defaultdict(Counter)
    rows = []
    for event in events:
        event_time = float(event["time_seconds"])
        for person in event.get("people", []):
            box = person.get("bbox_xyxy", [])
            for action in person.get("actions", []):
                label = str(action["label"])
                score = float(action["score"])
                labels[label] += 1
                scores[label].append(score)
                minute_counts[int(event_time // 60)][label] += 1
                rows.append({
                    "time_seconds": round(event_time, 3),
                    "time_mm_ss": f"{int(event_time // 60):02d}:{int(event_time % 60):02d}",
                    "label": label,
                    "confidence": round(score, 4),
                    "x1": round(float(box[0]), 1) if len(box) == 4 else "",
                    "y1": round(float(box[1]), 1) if len(box) == 4 else "",
                    "x2": round(float(box[2]), 1) if len(box) == 4 else "",
                    "y2": round(float(box[3]), 1) if len(box) == 4 else "",
                    "chunk_index": event.get("chunk_index", ""),
                })

    events_path = Path(args.events)
    csv_path = events_path.with_name("action-events.csv")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        fields = [
            "time_seconds", "time_mm_ss", "label", "confidence",
            "x1", "y1", "x2", "y2", "chunk_index"
        ]
        table = csv.DictWriter(stream, fieldnames=fields)
        table.writeheader()
        table.writerows(rows)

    summary = {
        "event_rows": len(rows),
        "detected_action_counts": dict(labels),
        "mean_confidence_by_label": {
            label: round(sum(values) / len(values), 4)
            for label, values in scores.items()
        },
        "counts_by_minute": {
            str(minute): dict(counts)
            for minute, counts in sorted(minute_counts.items())
        },
        "note": "Predictions are model outputs; review against the source recording before treating them as classroom evidence.",
    }
    events_path.with_name("action-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        current_time = frame_index / fps
        insertion = bisect.bisect_left(times, current_time)
        candidates = [idx for idx in (insertion - 1, insertion) if 0 <= idx < len(events)]
        nearest = min(candidates, key=lambda idx: abs(times[idx] - current_time)) if candidates else None
        if nearest is not None and abs(times[nearest] - current_time) <= 0.65:
            event = events[nearest]
            for person in event.get("people", []):
                box = person.get("bbox_xyxy", [])
                if len(box) != 4:
                    continue
                x1, y1, x2, y2 = [int(round(value)) for value in box]
                x1, x2 = max(0, x1), min(width - 1, x2)
                y1, y2 = max(0, y1), min(height - 1, y2)
                actions = sorted(
                    person.get("actions", []),
                    key=lambda item: float(item["score"]),
                    reverse=True,
                )[:3]
                color = PALETTE[nearest % len(PALETTE)]
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                for line, action in enumerate(actions):
                    text = f"{action['label']}: {float(action['score']):.2f}"
                    baseline = max(20, y1 - 8 - 22 * line)
                    cv2.putText(
                        frame, text, (x1, baseline),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2,
                        cv2.LINE_AA,
                    )
        clock = f"{int(current_time // 60):02d}:{int(current_time % 60):02d}"
        cv2.putText(
            frame, f"MM-TBA action detection  {clock}", (14, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (245, 245, 245), 2,
            cv2.LINE_AA,
        )
        writer.write(frame)
        frame_index += 1

    capture.release()
    writer.release()
    print(f"Rendered {frame_index} source frames at {fps:.3f} fps")
    print(f"Saved {len(rows)} timestamped action rows to {csv_path}")


if __name__ == "__main__":
    main()
