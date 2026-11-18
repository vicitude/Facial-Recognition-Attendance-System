"""S5 多人识别纯内存适配层。"""
from dataclasses import dataclass
from math import isfinite
from typing import Optional

from attendance.face_recognition_templates import identify


def normalize_box(box):
    if box is None or len(box) < 4:
        raise ValueError("INVALID_FACE_BOX")
    values = tuple(int(float(v)) for v in box[:4])
    if min(values) < 0 or values[2] <= values[0] or values[3] <= values[1]:
        raise ValueError("INVALID_FACE_BOX")
    return values


def iou(left, right):
    lx1, ly1, lx2, ly2 = left
    rx1, ry1, rx2, ry2 = right
    ix1, iy1, ix2, iy2 = max(lx1, rx1), max(ly1, ry1), min(lx2, rx2), min(ly2, ry2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_l = (lx2-lx1) * (ly2-ly1)
    area_r = (rx2-rx1) * (ry2-ry1)
    return inter / float(area_l + area_r - inter) if area_l + area_r - inter else 0.0

@dataclass(frozen=True)
class RecognitionResult:
    status: str
    employee_id: Optional[str]
    distance: Optional[float]
    pose: Optional[str]
    box: tuple


def recognize_faces(queries, employee_ids, threshold=1.0, overlap_threshold=0.5, key=None):
    results = []
    kept = []
    for raw_box, vector in queries:
        try:
            box = normalize_box(raw_box)
        except Exception:
            results.append(RecognitionResult("invalid", None, None, None, (0, 0, 0, 0)))
            continue
        if any(iou(box, old) >= overlap_threshold for old in kept):
            continue
        kept.append(box)
        try:
            match = identify(vector, employee_ids, threshold=threshold, key=key)
            if match is None:
                results.append(RecognitionResult("unknown", None, None, None, box))
            else:
                employee, distance, pose = match
                if not isfinite(distance) or distance < 0:
                    raise ValueError("INVALID_EMBEDDING")
                results.append(RecognitionResult("matched", employee.employee_id, distance, pose, box))
        except Exception:
            results.append(RecognitionResult("invalid", None, None, None, box))
    return results
