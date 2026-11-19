import numpy as np
import pytest

from attendance.active_liveness_features import (
    build_action_feature,
    eye_aspect_ratio,
    head_pitch_degrees,
    head_yaw_degrees,
)


def points(nose_x=0.5, chin_y=0.8):
    return {"left_eye": (0.4, 0.4), "right_eye": (0.6, 0.4), "nose": (nose_x, 0.55), "chin": (0.5, chin_y)}


def test_head_angles_and_feature_contract():
    assert head_yaw_degrees(points(0.6)) > 0
    assert head_pitch_degrees(points(chin_y=0.9)) > 0
    feature = build_action_feature(points())
    assert feature["face_count"] == 1
    assert feature["identity_continuous"] is True


def test_eye_aspect_ratio_and_validation():
    eye = np.array([[0, 0], [1, -1], [2, -1], [4, 0], [2, 1], [1, 1]], dtype=float)
    assert eye_aspect_ratio(eye) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        head_yaw_degrees({"left_eye": (0, 0), "right_eye": (0, 0), "nose": (0, 1)})
