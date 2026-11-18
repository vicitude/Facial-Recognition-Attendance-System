"""??????????????????????"""

import argparse
from dataclasses import asdict
import json
import sys
from time import perf_counter

import cv2
import numpy as np

from attendance.liveness_research import LivenessResearch, MultiFrameConsistency


def main():
    parser = argparse.ArgumentParser(description="S1 ?????????????????")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image")
    source.add_argument("--camera", type=int)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames ?????")
    sys.argv = [sys.argv[0]]
    import recognition
    started = perf_counter()
    engine = LivenessResearch()
    print(json.dumps({"event": "loaded", "liveness_load_ms": round((perf_counter()-started)*1000, 2), "research_only": True}))

    sequence = MultiFrameConsistency()

    def analyze(frame):
        started = perf_counter()
        boxes = recognition.recognition(frame)
        detection_ms = (perf_counter()-started)*1000
        evaluated = engine.evaluate(frame, boxes)
        result = asdict(evaluated)
        result["sequence_status"] = sequence.update(evaluated)
        result["detection_ms"] = detection_ms
        result["face_count"] = len(boxes)
        print(json.dumps(result), flush=True)

    if args.image:
        frame = cv2.imdecode(np.fromfile(args.image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("??????")
        analyze(frame)
    else:
        capture = cv2.VideoCapture(args.camera)
        try:
            if not capture.isOpened():
                raise RuntimeError("???????")
            for _ in range(args.frames):
                available, frame = capture.read()
                if not available:
                    raise RuntimeError("???????")
                analyze(frame)
        finally:
            capture.release()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"??????: {error}", file=sys.stderr)
        raise SystemExit(1)
