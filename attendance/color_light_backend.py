"""彩光单帧事实：同一张人脸执行现有模型门禁和 ROI 统计。"""
from time import monotonic

import cv2
import numpy as np
from PIL import Image


class ColorLightBackend:
    def __init__(self, templates, *, detect=None, embed=None, passive=None, quality=None):
        self._templates = np.asarray(tuple(templates), dtype=np.float32)
        if self._templates.shape != (3, 128) or not np.isfinite(self._templates).all():
            raise ValueError("COLOR_IDENTITY_REJECTED")
        if detect is None:
            from recognition import recognition
            from torch import inference_mode
            detect = inference_mode()(recognition)
        if embed is None:
            from facenet.facenet import Facenet
            embed = Facenet().extract_embedding
        if passive is None or quality is None:
            from attendance.liveness_research import LivenessResearch, assess_quality
            if passive is None:
                passive = LivenessResearch().evaluate
            if quality is None:
                quality = assess_quality
        self._detect, self._embed, self._passive, self._quality = detect, embed, passive, quality
        self._previous = None

    def __call__(self, frame) -> dict:
        start = monotonic()
        facts = dict(face_count=0, quality_ok=False, identity_vector=None,
                     identity_distance=None, passive_status="not_evaluated",
                     mean_rgb=(0.0, 0.0, 0.0), motion_score=0.0, timings_ms={})
        if (isinstance(frame, np.ndarray) and frame.dtype == np.uint8 and frame.ndim == 3
                and frame.shape[2] == 3 and min(frame.shape[:2]) > 1):
            boxes = self._detect(frame)
            facts["face_count"] = len(boxes)
            if len(boxes) == 1:
                height, width = frame.shape[:2]
                x1, y1, x2, y2 = [int(round(float(v))) for v in boxes[0][:4]]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(width, x2), min(height, y2)
                if x1 < x2 and y1 < y2:
                    self._measure(frame, (x1, y1, x2, y2), facts)
        if not facts["quality_ok"]:
            self._previous = None
        facts["timings_ms"]["color_stats_ms"] = (monotonic() - start) * 1000
        return facts

    def _measure(self, frame, box, facts):
        x1, y1, x2, y2 = box
        facts["quality_ok"] = bool(self._quality(frame, box)[0])
        if not facts["quality_ok"]:
            return
        height, width = frame.shape[:2]
        position = np.array([x1 / width, y1 / height, x2 / width, y2 / height])
        if self._previous is not None:
            facts["motion_score"] = float(np.max(np.abs(position - self._previous)))
        self._previous = position
        crop = frame[y1:y2, x1:x2]
        h, w = crop.shape[:2]
        roi = crop[int(h * .15):int(h * .85), int(w * .20):int(w * .80)]
        if not roi.size:
            facts["quality_ok"] = False
            return
        facts["mean_rgb"] = tuple(float(v) for v in roi.mean(axis=(0, 1))[::-1])
        vector = np.asarray(self._embed(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))))
        if vector.shape == (128,) and vector.dtype == np.float32 and np.isfinite(vector).all():
            facts["identity_vector"] = vector
            facts["identity_distance"] = float(np.min(np.linalg.norm(self._templates - vector, axis=1)))
        facts["passive_status"] = self._passive(frame, [box]).status
