"""三姿态人脸模板的纯数据契约与登记质量规则。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import cv2
import numpy as np


class FacePose(str, Enum):
    FRONTAL = "frontal"
    LEFT_45 = "left_45"
    RIGHT_45 = "right_45"


POSE_PROMPTS = {
    FacePose.FRONTAL: "请正面看向摄像头",
    FacePose.LEFT_45: "请左转45度后点击采集",
    FacePose.RIGHT_45: "请右转45度后点击采集",
}


@dataclass(frozen=True)
class QualityResult:
    ok: bool
    reason: str
    face_count: int
    face_width: int = 0
    face_height: int = 0
    brightness: float = 0.0
    sharpness: float = 0.0


def assess_registration_quality(
    frame: np.ndarray,
    boxes: Sequence[Sequence[int]],
    *,
    min_face_size: int = 80,
    min_brightness: float = 25.0,
    max_brightness: float = 235.0,
    min_sharpness: float = 30.0,
) -> QualityResult:
    """登记单帧质量门：恰好一脸、尺寸、亮度、清晰度。"""
    if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
        return QualityResult(False, "输入画面格式无效", len(boxes))
    if len(boxes) != 1:
        return QualityResult(False, "必须恰好检测到一张脸", len(boxes))
    raw_box = boxes[0]
    # YOLO 当前返回 [x1,y1,x2,y2,score,class,label]；兼容旧版带 label 前缀格式。
    if len(raw_box) >= 7:
        raw_box = raw_box[:4]
    elif len(raw_box) >= 5 and isinstance(raw_box[0], str):
        raw_box = raw_box[1:5]
    box = [int(float(v)) for v in raw_box]
    if len(box) != 4:
        return QualityResult(False, "人脸框格式无效", len(boxes))
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    width, height = x2 - x1, y2 - y1
    if width < min_face_size or height < min_face_size:
        return QualityResult(False, "人脸太小，请靠近摄像头", 1, width, height)
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if brightness < min_brightness or brightness > max_brightness:
        return QualityResult(False, "亮度不合格，请调整光线", 1, width, height, brightness, sharpness)
    if sharpness < min_sharpness:
        return QualityResult(False, "画面不够清晰，请保持稳定后重拍", 1, width, height, brightness, sharpness)
    return QualityResult(True, "ok", 1, width, height, brightness, sharpness)
