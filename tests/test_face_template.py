"""三姿态登记质量与提示契约测试。"""

import cv2
import numpy as np

from attendance.face_template import FacePose, POSE_PROMPTS, assess_registration_quality


def _frame(value=120):
    frame = np.full((240, 320, 3), value, dtype=np.uint8)
    cv2.rectangle(frame, (80, 50), (240, 210), (0, 0, 255), 2)
    return frame


def test_pose_prompts_explicitly_use_45_degrees():
    assert "左转头约45°" in POSE_PROMPTS[FacePose.LEFT_45]
    assert "右转头约45°" in POSE_PROMPTS[FacePose.RIGHT_45]
    assert "90°" in POSE_PROMPTS[FacePose.LEFT_45]


def test_quality_requires_exactly_one_face():
    result = assess_registration_quality(_frame(), [])
    assert not result.ok
    assert "恰好" in result.reason


def test_quality_rejects_small_face_and_accepts_clear_face():
    small = assess_registration_quality(_frame(), [(10, 10, 50, 50)])
    assert not small.ok
    clear = assess_registration_quality(_frame(), [(80, 50, 240, 210)])
    assert clear.ok
    assert clear.face_width == 160


def test_quality_rejects_bad_brightness_and_blur():
    dark = assess_registration_quality(_frame(5), [(80, 50, 240, 210)])
    assert not dark.ok
    blurred = np.full((240, 320, 3), 120, dtype=np.uint8)
    blurred_result = assess_registration_quality(blurred, [(80, 50, 240, 210)])
    assert not blurred_result.ok
