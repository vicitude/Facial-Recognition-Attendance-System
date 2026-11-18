"""SPEC-011：只使用内存替身，不读设备、模板库或密钥。"""
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PyQt5 import QtCore


@pytest.fixture
def scenario(qtbot, monkeypatch):
    detector = ModuleType('recognition')
    detector.recognition = Mock(return_value=[[0, 0, 80, 80]])
    monkeypatch.setitem(sys.modules, 'recognition', detector)
    from attendance import ui_checkin as ui
    from attendance import liveness_research
    from attendance.recognition_results import RecognitionResult

    confirmed = []

    class Confirm:
        recorded = SimpleNamespace(connect=lambda callback: None)

        def __init__(self, *, parent, employee_id, name):
            confirmed.append((employee_id, QtCore.QThread.currentThread()))

        def exec_(self):
            return 0

    tab = ui.CheckInTab()
    qtbot.addWidget(tab)
    frame = np.zeros((80, 260, 3), dtype=np.uint8)
    monkeypatch.setattr(ui.recognition, 'recognition', detector.recognition)
    monkeypatch.setattr(ui.EmployeeService, 'list_all', lambda **kw: [])
    monkeypatch.setattr(ui.EmployeeService, 'get', lambda eid: SimpleNamespace(employee_id=eid, name=eid, is_active=True))
    monkeypatch.setattr(ui, 'load_or_create_key', lambda path: b'test')
    monkeypatch.setattr(ui, 'CheckConfirmDialog', Confirm)
    monkeypatch.setattr(ui.QtWidgets.QMessageBox, 'warning', Mock())
    tab._template_facenet = SimpleNamespace(extract_embedding=lambda image: None)

    def match(queries, employees, *, key):
        return [RecognitionResult('matched', str(i), .1, 'front', tuple(box)) for i, (box, _) in enumerate(queries)]

    monkeypatch.setattr(ui, 'recognize_faces', match)
    model = Mock()
    model.evaluate.return_value = SimpleNamespace(status='live_candidate')
    factory = Mock(return_value=model)
    monkeypatch.setattr(liveness_research, 'LivenessResearch', factory)
    return SimpleNamespace(ui=ui, tab=tab, model=model, factory=factory, frame=frame,
                           detector=detector.recognition, confirmed=confirmed)


@pytest.mark.parametrize('status,expected', [
    ('live_candidate', None), ('spoof_candidate', '未通过真人检测'),
    ('low_confidence', '调整光线'), ('low_quality', '调整光线'),
    ('inconclusive', '调整光线'), ('no_face', '调整光线'),
    ('multiple_faces', '调整光线'), ('unknown_status', '调整光线'),
    ('load_error', '暂不可用'), ('evaluate_error', '暂不可用'),
])
def test_PT_PAS_01_only_live_can_confirm(scenario, status, expected):
    s = scenario
    s.detector.return_value += [[90, 0, 170, 80]]
    s.model.evaluate.return_value = SimpleNamespace(status=status)
    if status == 'load_error':
        s.factory.side_effect = FileNotFoundError('private detail')
    elif status == 'evaluate_error':
        s.model.evaluate.side_effect = RuntimeError('private detail')
    s.tab.flag_recognition = True
    s.tab._do_recognition(s.frame)
    assert s.factory.call_count == 1
    if status != 'load_error':
        [(args, _)] = s.model.evaluate.call_args_list
        assert args[0] is s.frame
        assert args[1] == [(0, 0, 80, 80)]
    else:
        assert s.tab._passive_liveness is None
        s.model.evaluate.assert_not_called()
    if expected is None:
        assert [eid for eid, _ in s.confirmed] == ['0']
    else:
        assert not s.confirmed
        assert expected in s.tab.result_detail.text()
        assert 'private detail' not in s.tab.result_detail.text()
        assert not s.tab.flag_recognition


def test_PT_PAS_01_no_match_does_not_load(scenario, monkeypatch):
    s = scenario
    monkeypatch.setattr(s.ui, 'recognize_faces', lambda *args, **kw: [])
    s.tab._do_recognition(s.frame)
    s.factory.assert_not_called()
    assert not s.confirmed


@pytest.mark.parametrize('middle', ['spoof_candidate', RuntimeError('inference error')])
def test_PT_PAS_02_mixed_queue_keeps_only_passed_in_order(scenario, qtbot, middle):
    s = scenario
    boxes = [(0, 0, 80, 80), (90, 0, 170, 80), (180, 0, 260, 80)]
    live = SimpleNamespace(status='live_candidate')
    s.model.evaluate.side_effect = [live, middle if isinstance(middle, Exception) else SimpleNamespace(status=middle), live]
    results = s.tab._identify_frame_boxes(s.frame, boxes)
    assert not results[1].employee_id
    assert [call.args[1] for call in s.model.evaluate.call_args_list] == [[box] for box in boxes]
    s.tab._handle_recognition_results(results)
    assert [row.employee_id for row in s.tab._multi_queue] == ['0', '2']
    qtbot.waitUntil(lambda: not s.tab._multi_processing)
    assert [eid for eid, _ in s.confirmed] == ['0', '2']


@pytest.mark.parametrize('mode', ['color_liveness', 'liveness'])
def test_TC_PAS_03_trials_run_only_their_own_gate(scenario, monkeypatch, mode):
    s = scenario
    setter = getattr(s.tab, f'set_{mode}_enabled')
    assert setter(True)
    verify = Mock(side_effect=[False, True])
    monkeypatch.setattr(s.tab, f'_verify_{mode}', verify)
    s.tab._do_recognition(s.frame)
    assert not s.confirmed
    s.tab._do_recognition(s.frame)
    assert [eid for eid, _ in s.confirmed] == ['0']
    s.factory.assert_not_called()
    s.model.evaluate.assert_not_called()
    assert setter(False)
    assert s.tab.liveness_status.text() == '普通模式：被动活体检测'


def test_TC_PAS_04_background_gate_and_model_cache(scenario, qtbot):
    s = scenario
    main = QtCore.QThread.currentThread()
    threads = []

    def evaluate(frame, boxes):
        assert frame is not s.frame
        np.testing.assert_array_equal(frame, s.frame)
        assert boxes == [(0, 0, 80, 80)]
        threads.append(QtCore.QThread.currentThread() != main)
        return SimpleNamespace(status='live_candidate')

    s.model.evaluate.side_effect = evaluate
    for count in (1, 2):
        s.tab.flag_recognition = True
        s.tab._submit_recognition(s.frame)
        qtbot.waitUntil(lambda: not s.tab._recognition_busy and len(s.confirmed) == count)
    assert threads == [True, True]
    assert s.confirmed == [('0', main), ('0', main)]
    assert s.factory.call_count == 1


def test_TC_PAS_04_stale_or_bare_result_cannot_confirm(scenario):
    s = scenario
    s.tab.flag_recognition = True
    accepted = s.tab._identify_frame_boxes(s.frame, [(0, 0, 80, 80)])
    s.tab._on_worker_finished(-1, accepted)
    s.tab._on_worker_finished(0, '0')
    assert not s.confirmed
    assert s.tab.result_name.text() == '活体未通过'
