"""主动活体关键点特征适配器。

输入为上层关键点检测器提供的归一化关键点，不负责检测模型和视频存储。
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np


def _points(points: Mapping[str, Iterable[float]]) -> dict[str, np.ndarray]:
    result = {name: np.asarray(value, dtype=float) for name, value in points.items()}
    if not result or any(value.shape != (2,) or not np.isfinite(value).all() for value in result.values()):
        raise ValueError("关键点必须是有限的二维坐标")
    return result


def head_yaw_degrees(points: Mapping[str, Iterable[float]]) -> float:
    """用双眼中点到鼻尖的水平偏移估算左右转头角度，正值为右偏。"""
    p = _points(points)
    required = ("left_eye", "right_eye", "nose")
    if any(name not in p for name in required):
        raise ValueError("缺少眼睛或鼻尖关键点")
    eyes = (p["left_eye"] + p["right_eye"]) / 2.0
    span = float(np.linalg.norm(p["right_eye"] - p["left_eye"]))
    if span <= 1e-6:
        raise ValueError("双眼距离无效")
    return float(math.degrees(math.atan2(p["nose"][0] - eyes[0], span)))


def head_pitch_degrees(points: Mapping[str, Iterable[float]]) -> float:
    """用眼睛中点到下巴的垂直关系估算点头角度。"""
    p = _points(points)
    required = ("left_eye", "right_eye", "chin")
    if any(name not in p for name in required):
        raise ValueError("缺少眼睛或下巴关键点")
    eyes = (p["left_eye"] + p["right_eye"]) / 2.0
    span = float(np.linalg.norm(p["right_eye"] - p["left_eye"]))
    if span <= 1e-6:
        raise ValueError("双眼距离无效")
    return float(math.degrees(math.atan2(p["chin"][1] - eyes[1], span)))


def eye_aspect_ratio(eye: np.ndarray) -> float:
    """六点眼睛关键点的 EAR；点序为左右端点和上下两组点。"""
    eye = np.asarray(eye, dtype=float)
    if eye.shape != (6, 2) or not np.isfinite(eye).all():
        raise ValueError("眼睛关键点必须是 6x2")
    horizontal = np.linalg.norm(eye[0] - eye[3])
    if horizontal <= 1e-6:
        raise ValueError("眼睛水平跨度无效")
    return float((np.linalg.norm(eye[1] - eye[5]) + np.linalg.norm(eye[2] - eye[4])) / (2 * horizontal))


def build_action_feature(points: Mapping[str, Iterable[float]], *, eye: np.ndarray | None = None, identity_continuous: bool = True) -> dict:
    feature = {
        "face_count": 1,
        "yaw_deg": head_yaw_degrees(points),
        "pitch_deg": head_pitch_degrees(points),
        "identity_continuous": identity_continuous,
    }
    if eye is not None:
        feature["ear"] = eye_aspect_ratio(eye)
    return feature
