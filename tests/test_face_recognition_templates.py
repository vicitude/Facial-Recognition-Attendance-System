import numpy as np
from unittest.mock import patch

from attendance.face_recognition_templates import identify, l2_distance, match_employee


def test_l2_distance_128_vector():
    assert np.isclose(l2_distance(np.zeros(128, np.float32), np.ones(128, np.float32)), np.sqrt(128))


def test_match_employee_uses_smallest_pose_distance():
    query = np.zeros(128, np.float32)
    vectors = {"frontal": np.ones(128, np.float32), "left_45": np.zeros(128, np.float32), "right_45": np.full(128, 2, np.float32)}
    with patch("attendance.face_recognition_templates.FaceTemplateService.load_employee_vectors", return_value=vectors):
        assert match_employee(query, "100001", key=b"k" * 32) == (0.0, "left_45")
