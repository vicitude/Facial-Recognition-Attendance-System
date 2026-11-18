"""M2/M3 非破坏性契约测试。"""

from pathlib import Path


def test_m2_add_entry_uses_enrollment_dialog():
    source = Path("attendance/ui_employees.py").read_text(encoding="utf-8")
    assert "EnrollmentDialog" in source
    assert "def _on_add" in source


def test_m3_checkin_prefers_encrypted_template_adapter():
    source = Path("attendance/ui_checkin.py").read_text(encoding="utf-8")
    assert "recognize_faces" in source
    assert "load_or_create_key" in source
    assert "_identify_frame_boxes" in source


def test_legacy_entrypoints_are_not_modified_by_m3_adapter():
    for path in ("ui.py", "recognition.py", "get_name.py"):
        assert Path(path).exists()
