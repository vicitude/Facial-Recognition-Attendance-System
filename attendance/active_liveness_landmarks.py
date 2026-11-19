"""真实关键点检测适配层。

优先使用可选 MediaPipe Face Mesh；本项目默认环境未强制新增依赖。
检测器输出统一关键点契约，再交给 active_liveness_features。
"""
from __future__ import annotations

from typing import Any

import numpy as np

from attendance.active_liveness_features import build_action_feature


class LandmarkBackendUnavailable(RuntimeError):
    pass


class FaceLandmarkDetector:
    """MediaPipe Face Mesh 适配器；不保存帧。"""

    def __init__(self, max_faces: int = 1, min_detection_confidence: float = 0.6):
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise LandmarkBackendUnavailable(
                "未安装 mediapipe，无法启用真实关键点检测；请在已确认的环境中单独安装"
            ) from exc
        self._mp = mp
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=max_faces,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_detection_confidence,
        )

    def close(self) -> None:
        self._mesh.close()

    def detect(self, frame: np.ndarray) -> dict[str, Any]:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame 必须是 BGR 三通道图像")
        height, width = frame.shape[:2]
        rgb = frame[:, :, ::-1]
        result = self._mesh.process(rgb)
        faces = result.multi_face_landmarks or []
        if len(faces) != 1:
            return {"face_count": len(faces)}
        points = faces[0].landmark
        def xy(index: int) -> tuple[float, float]:
            return (float(points[index].x * width), float(points[index].y * height))
        # MediaPipe Face Mesh: eyes/nose/chin plus six-point eye contours.
        left_eye = xy(33)
        right_eye = xy(263)
        nose = xy(1)
        chin = xy(152)
        left_eye6 = np.asarray([xy(i) for i in (33, 160, 158, 133, 153, 144)], dtype=float)
        right_eye6 = np.asarray([xy(i) for i in (263, 387, 385, 362, 380, 373)], dtype=float)
        feature = build_action_feature(
            {"left_eye": left_eye, "right_eye": right_eye, "nose": nose, "chin": chin},
            eye=left_eye6,
        )
        feature["right_eye_points"] = right_eye6
        coordinates = np.asarray([xy(i) for i in range(len(points))])
        feature["face_box"] = (float(coordinates[:, 0].min()), float(coordinates[:, 1].min()),
                               float(coordinates[:, 0].max()), float(coordinates[:, 1].max()))
        return feature
