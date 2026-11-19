import numpy as np
import pytest

from attendance.active_liveness_landmarks import FaceLandmarkDetector, LandmarkBackendUnavailable


def test_backend_reports_missing_optional_dependency_cleanly(monkeypatch):
    import builtins
    original_import = builtins.__import__
    def blocked(name, *args, **kwargs):
        if name == "mediapipe":
            raise ImportError("blocked for contract test")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(LandmarkBackendUnavailable, match="mediapipe"):
        FaceLandmarkDetector()


def test_invalid_frame_rejected_without_backend():
    # Constructor may be unavailable; validate public error contract through a tiny fake instance.
    detector = object.__new__(FaceLandmarkDetector)
    detector._mesh = None
    with pytest.raises(ValueError):
        detector.detect(np.zeros((10, 10), dtype=np.uint8))
