def test_multi_result_rows_have_employee_ids(qtbot):
    from attendance.ui_checkin import CheckInTab
    tab = CheckInTab()
    tab.flag_recognition = True
    tab._stop_recognition_after_unknown = lambda: None
    from attendance.recognition_results import RecognitionResult
    rows = [
        RecognitionResult('live_candidate', '100001', 0.22, 'front', (0, 0, 80, 80)),
        RecognitionResult('live_candidate', '100002', 0.31, 'front', (90, 0, 170, 80)),
    ]
    tab._on_worker_finished(0, rows)
    assert not tab.multi_results.isHidden()
    assert tab.multi_results.count() == 2
    assert tab.multi_results.item(0).data(256) == "100001"
    assert tab.multi_results.item(1).data(256) == "100002"
    tab.close()


def test_multi_flow_is_queue_based_not_selection():
    from pathlib import Path
    source = Path("attendance/ui_checkin.py").read_text(encoding="utf-8")
    assert "self._multi_queue = matched" in source
    assert "QtCore.QTimer.singleShot(0, self._process_next_multi)" in source
    assert "itemDoubleClicked.connect" not in source


def test_employee_edit_does_not_require_photo_or_schedule():
    from pathlib import Path
    source = Path("attendance/ui_employees.py").read_text(encoding="utf-8")
    assert 'self._mode == "add" and (not face_path or schedule_id_raw is None)' in source
    assert "face_image_path=face_path" in source


def test_enrollment_prompt_and_reset_contract():
    from pathlib import Path
    source = Path("attendance/ui_enrollment.py").read_text(encoding="utf-8")
    assert "请左转45度后点击采集" in source
    assert "请右转45度后点击采集" in source
    assert 'self.capture_btn.setText("重新采集")' in source
    assert "self._reset_capture_sequence" in source
