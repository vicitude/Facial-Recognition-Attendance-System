"""SPEC-008 当轮活体门禁；全替身，不启用设备。"""
import sys
from types import SimpleNamespace
import numpy as np
import pytest
from PyQt5 import QtCore, QtWidgets


@pytest.fixture
def tab(qapp, monkeypatch):
    from attendance import ui_checkin as ui
    monkeypatch.setattr(ui.EmployeeService, 'get', lambda eid: SimpleNamespace(employee_id=eid, name=eid, is_active=True))
    widget = ui.CheckInTab()
    calls = []
    class Confirm:
        recorded = SimpleNamespace(connect=lambda f: None)
        def __init__(self, **kw): calls.append(kw['employee_id'])
        def exec_(self): return 0
    monkeypatch.setattr(ui, 'CheckConfirmDialog', Confirm)
    yield widget, calls
    widget.deleteLater()


@pytest.mark.parametrize('current,busy', [(False, False), (True, False), (False, True), (True, True)])
def test_CT_LCI_05_admin_capsule(tab, monkeypatch, current, busy):
    from attendance.ui_admins import AdminsTab, AdminService
    from attendance.ui_main import MainWindow
    widget, _ = tab
    monkeypatch.setattr(AdminService, 'list_all', lambda: [])
    admins = AdminsTab(SimpleNamespace(id=1))
    action = QtWidgets.QAction(None)
    action.setCheckable(True)
    status = SimpleNamespace(showMessage=lambda message: None)
    host = SimpleNamespace(checkin_tab=widget, admins_tab=admins, action_liveness=action, statusBar=lambda: status)
    requests = []
    admins.liveness_requested.connect(requests.append)
    admins.liveness_requested.connect(lambda enabled: MainWindow._on_liveness_toggled(host, enabled))
    widget.set_liveness_enabled(current)
    admins.set_liveness_state(current)
    assert not requests
    widget._multi_processing = busy
    admins.btn_liveness.click()
    expected = current if busy else not current
    assert widget.liveness_enabled == admins.btn_liveness.isChecked() == action.isChecked() == expected
    assert admins.btn_liveness.text() == ('活体试运行：开启' if expected else '活体试运行：关闭')
    admins.btn_liveness.click()
    assert widget.liveness_enabled == current
    widget._multi_processing = False
    admins.deleteLater()


@pytest.mark.parametrize('enabled,verified,expected', [(False, False, 0), (True, False, 0), (True, True, 1)])
def test_PT_LCI_01_gate(tab, monkeypatch, enabled, verified, expected):
    widget, calls = tab
    widget.liveness_enabled = enabled
    monkeypatch.setattr(widget, '_verify_liveness', lambda emp: verified)
    widget._handle_recognition_name('111111')
    assert len(calls) == expected


def test_CT_LCI_02_each_employee_new_check(tab, monkeypatch, qapp):
    widget, calls = tab
    widget.liveness_enabled = True
    seen = []
    def verify(emp):
        seen.append(emp.employee_id)
        return emp.employee_id == '222222'
    monkeypatch.setattr(widget, '_verify_liveness', verify)
    widget._multi_processing = True
    from attendance.recognition_results import RecognitionResult
    widget._multi_queue = [RecognitionResult('matched', eid, .1, 'front', (0, 0, 80, 80))
                           for eid in ('111111', '222222')]
    widget._process_next_multi()
    qapp.processEvents()
    qapp.processEvents()
    assert seen == ['111111', '222222']
    assert calls == ['222222']


def test_CT_LCI_02_switch_and_stop(tab):
    widget, _ = tab
    assert not widget.liveness_enabled
    assert widget.set_liveness_enabled(True)
    widget._multi_processing = True
    assert not widget.set_liveness_enabled(False)
    widget._multi_queue = ['111111']
    widget._on_stop_clicked()
    assert not widget._multi_queue and not widget._multi_processing


def test_UT_LCI_03_bound_vectors(monkeypatch):
    # 导入生产模块不会初始化模型；环境已有推理依赖。
    monkeypatch.delitem(sys.modules, 'attendance.liveness_backend', raising=False)
    monkeypatch.setattr(sys, 'argv', sys.argv[:1])
    from attendance.liveness_backend import BoundAuxiliary
    bound = BoundAuxiliary([np.zeros(128)] * 3)
    assert bound.matches(np.zeros(128))
    vector = np.zeros(128); vector[0] = 1
    assert not bound.matches(vector)
    assert not bound.matches(np.full(128, np.nan))
    with pytest.raises(ValueError): BoundAuxiliary([np.zeros(128)])


def test_PT_LCI_01_employee_inactive_after_check(tab, monkeypatch):
    from attendance import ui_checkin as ui
    widget, calls = tab
    widget.liveness_enabled = True
    monkeypatch.setattr(widget, '_verify_liveness', lambda emp: True)
    reads = iter([True, False])
    monkeypatch.setattr(ui.EmployeeService, 'get', lambda eid: SimpleNamespace(employee_id=eid, name=eid, is_active=next(reads)))
    widget._handle_recognition_name('111111')
    assert not calls


def test_CT_LCI_04_exec_error_shutdown_before_resume(tab, monkeypatch):
    from attendance import ui_checkin as ui
    from attendance import ui_liveness
    widget, _ = tab
    events = []
    widget._camera = object()
    widget._timer = SimpleNamespace(stop=lambda: events.append('pause'), start=lambda: events.append('resume'))
    class Dialog:
        def __init__(self, *args): pass
        def exec_(self): raise RuntimeError('test')
        def _shutdown(self): events.append('shutdown')
    monkeypatch.setattr(ui_liveness, 'LivenessDialog', Dialog)
    monkeypatch.setattr(ui, 'show_error', lambda *args: None)
    assert not widget._verify_liveness(SimpleNamespace(employee_id='111111', name='A'))
    assert events == ['pause', 'shutdown', 'resume']
    widget._camera = widget._timer = None


def test_CT_LCI_04_done_cannot_forge_pass(qapp):
    from attendance.ui_liveness import LivenessDialog
    dialog = LivenessDialog.__new__(LivenessDialog)
    QtWidgets.QDialog.__init__(dialog)
    dialog.verified = False
    dialog.timer = QtCore.QTimer(dialog)
    dialog.camera = dialog.pipeline = None
    dialog.done(QtWidgets.QDialog.Accepted)
    assert dialog.result() == QtWidgets.QDialog.Rejected


@pytest.mark.parametrize('status,expected', [('passed', True), ('failed', False), ('timeout', False)])
def test_CT_LCI_04_tick_terminal(qapp, monkeypatch, status, expected):
    from attendance import ui_liveness as ui
    from attendance.fused_liveness import FusionResult
    dialog = ui.LivenessDialog.__new__(ui.LivenessDialog)
    QtWidgets.QDialog.__init__(dialog)
    dialog.verified = False
    from time import monotonic
    dialog.started_at = monotonic()
    dialog.timer = QtCore.QTimer(dialog)
    dialog.message = QtWidgets.QLabel()
    dialog.preview = QtWidgets.QLabel()
    closed = []
    result = FusionResult(status, 'blink', 'verification', 3, None)
    dialog.camera = SimpleNamespace(error=None, snapshot=lambda: (1, monotonic(), np.zeros((40, 40, 3), dtype=np.uint8)), close=lambda: closed.append('camera'))
    dialog.pipeline = SimpleNamespace(submit=lambda *a: None, snapshot=lambda: dict(result=result, metrics={}, warming=False), close=lambda: closed.append('pipeline'))
    monkeypatch.setattr(ui, 'draw_chinese_overlay', lambda frame, *args: frame)
    dialog._tick()
    assert dialog.verified is expected
    assert closed == ['camera', 'pipeline']
    assert dialog.result() == (QtWidgets.QDialog.Accepted if expected else QtWidgets.QDialog.Rejected)


def test_CT_LCI_04_timeout(qapp):
    from attendance.ui_liveness import LivenessDialog
    dialog = LivenessDialog.__new__(LivenessDialog)
    QtWidgets.QDialog.__init__(dialog)
    dialog.verified = False
    dialog.started_at = -100
    dialog.timer = QtCore.QTimer(dialog)
    closed = []
    dialog.camera = SimpleNamespace(error=None, close=lambda: closed.append('camera'))
    dialog.pipeline = SimpleNamespace(close=lambda: closed.append('pipeline'))
    dialog._tick()
    assert not dialog.verified and closed == ['camera', 'pipeline']


def test_CT_LCI_04_borrowed_capture():
    from attendance.ui_liveness import BorrowedCapture
    calls = []
    capture = SimpleNamespace(read=lambda: (True, 'frame'), release=lambda: calls.append('released'))
    borrowed = BorrowedCapture(capture)
    for _ in range(20):
        if borrowed.snapshot() is not None:
            break
        sleep(0.01)
    assert borrowed.snapshot() is not None
    borrowed.release()
    assert not calls
