import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5 import QtWidgets

from attendance import color_failure_log as log
from attendance.color_light_liveness import ColorLightConfig, ColorLivenessSession, ColorResult


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    path = tmp_path / 'failures.jsonl'
    monkeypatch.setattr(log, '_LOG_PATH', path)
    return path


def test_PT_CLR_13_append_baseline_failure_and_missing_data(log_path):
    config = ColorLightConfig()
    session = ColorLivenessSession('private-id', config)
    session.start(0)
    for index, pixel in enumerate((10, 250, 10), 1):
        result = session.submit(index, index / 10, dict(
            face_count=1, quality_ok=True, motion_score=0,
            identity_vector=np.zeros(128, np.float32), identity_distance=.1,
            passive_status='live_candidate', mean_rgb=(pixel,) * 3), 'white')
    assert result.reason == 'COLOR_UNRESPONSIVE'
    assert log.append_color_failure(result.reason, min_color_ratio=.85, config=config,
                                    snapshot={'result': result, 'frame': object(), 'frame_count': 9})
    assert log.append_color_failure('COLOR_LIVENESS_UNAVAILABLE', min_color_ratio=.9)
    text = log_path.read_text(encoding='utf-8')
    first, second = map(json.loads, text.splitlines())
    assert 'private-id' not in text and 'frame' not in first
    assert first['color'] == 'white' and first['frame_count'] == 9
    assert first['baseline_samples'] == 3 and first['baseline_luma_variance'] > .04
    assert first['baseline_chroma'] == pytest.approx([1 / 3] * 3)
    assert first['chroma_delta_threshold'] == .08
    assert second['baseline_chroma'] is None and second['color_diagnostics'] == []


@pytest.mark.parametrize('mode,expected', [('shown', 1), ('unseen', 1), ('cancel', 0), ('pass', 0), ('unwritable', 0)])
def test_CT_CLR_14_dialog_terminal_logging(log_path, qtbot, monkeypatch, mode, expected):
    from attendance import ui_color_liveness as ui

    monkeypatch.setattr(ui, 'load_or_create_key', lambda _: b'')
    monkeypatch.setattr(ui.FaceTemplateService, 'load_employee_vectors', lambda *_: {})
    status = {'cancel': 'rejected', 'pass': 'passed'}.get(mode, 'rejected')
    reason = {'cancel': 'COLOR_CANCELLED', 'pass': None}.get(mode, 'COLOR_UNRESPONSIVE')
    row = dict(cycle=1, color='green', samples=12, hits=0, motion_skips=1,
               quality_skips={'blurry': 2, 'private': 1}, delta_median=.02, delta_peak=.04)
    outcome = ColorResult(status, status, 'green', 0, 12, reason, {'color_diagnostics': [row]})
    snap = {'result': outcome}
    monkeypatch.setattr(ui, 'ColorLivenessWorker', lambda *args, **kwargs: SimpleNamespace(
        stop=lambda: True, snapshot=lambda: snap))
    if mode == 'unwritable':
        monkeypatch.setattr(log, '_LOG_PATH', log_path.parent)
    dialog = ui.ColorLivenessDialog('123456', 'private-name', None)
    qtbot.addWidget(dialog)
    if mode in ('shown', 'unwritable'):
        dialog._show_failure(reason, '测试', snap)
        assert reason in dialog.message.text()
    dialog.verified = mode == 'pass'
    dialog.done(QtWidgets.QDialog.Accepted)
    assert (dialog.result() == QtWidgets.QDialog.Accepted) == (mode == 'pass')
    lines = log_path.read_text(encoding='utf-8').splitlines() if log_path.exists() else []
    assert len(lines) == expected
    if lines:
        assert 'private' not in lines[0] and '123456' not in lines[0]
        assert json.loads(lines[0])['color_diagnostics'][0]['quality_skips'] == {'blurry': 2}


def test_CT_CLR_14_startup_failure(log_path, qtbot, monkeypatch):
    monkeypatch.setattr(sys, 'argv', sys.argv[:1])
    from attendance import ui_color_liveness as ui
    from attendance.ui_checkin import CheckInTab

    def fail(*args, **kwargs):
        raise RuntimeError('private details')

    monkeypatch.setattr(ui, 'ColorLivenessDialog', fail)
    tab = CheckInTab()
    qtbot.addWidget(tab)
    tab._camera = object()
    assert not tab._verify_color_liveness(SimpleNamespace(employee_id='123456', name='private-name'))
    text = log_path.read_text(encoding='utf-8')
    assert json.loads(text)['reason'] == 'COLOR_LIVENESS_UNAVAILABLE'
    assert 'private' not in text
    tab._camera = None
