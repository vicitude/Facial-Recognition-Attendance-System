from threading import Event, current_thread
from types import SimpleNamespace

import numpy as np
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets


def test_CT_CLR_11_ratio_is_passed_to_dialog(qtbot, monkeypatch):
    from attendance import ui_color_liveness as ui
    monkeypatch.setattr(ui, 'load_or_create_key', lambda _: b'')
    monkeypatch.setattr(ui.FaceTemplateService, 'load_employee_vectors', lambda *_: {})
    dialog = ui.ColorLivenessDialog('123456', '测试员工', None, min_color_ratio=0.90)
    assert dialog._config.min_color_ratio == 0.90
    dialog._shutdown()


def test_CT_CLR_09_shows_failed_color_counts(qtbot, monkeypatch):
    from attendance import ui_color_liveness as ui
    from attendance.color_light_liveness import ColorResult

    failed = ColorResult('rejected', 'rejected', 'green', 0, 10, 'COLOR_UNRESPONSIVE',
                         dict(baseline_samples=3, color_samples=5, color_hits=2, color_motion_skips=3))
    snapshot = dict(result=failed, frame_count=30, processed_count=20, valid_count=13)
    monkeypatch.setattr(ui, 'load_or_create_key', lambda _: b'')
    monkeypatch.setattr(ui.FaceTemplateService, 'load_employee_vectors', lambda *_: {})
    monkeypatch.setattr(ui, 'ColorLivenessWorker', lambda *a, **kw: SimpleNamespace(
        start=lambda: None, stop=lambda: True, snapshot=lambda: snapshot))
    dialog = ui.ColorLivenessDialog('123456', '测试员工', None)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._refresh()
    text = dialog.message.text()
    for fragment in ('COLOR_UNRESPONSIVE', '失败颜色：绿光', '本色有效 5 帧', '色差达标 2 帧', '位移丢弃 3 帧'):
        assert fragment in text
    assert not dialog.verified


def test_CT_CLR_04_preview_and_cancel_while_inference_is_blocked(qtbot, monkeypatch):
    from attendance import ui_color_liveness as ui
    from attendance.color_liveness_worker import ColorLivenessWorker

    entered, resume, capture_ended = Event(), Event(), Event()
    readers, releases, colors = set(), [], []

    def analyze(_):
        entered.set()
        assert resume.wait(4)
        return {}

    class Camera:
        index = 0

        def read(self):
            readers.add(current_thread().name)
            capture_ended.wait(.02)
            self.index += 1
            return True, np.full((40, 60, 3), self.index % 255, dtype=np.uint8)

        def release(self):
            releases.append(True)

    camera = Camera()
    monkeypatch.setattr(ui, 'load_or_create_key', lambda _: b'')
    monkeypatch.setattr(ui.FaceTemplateService, 'load_employee_vectors', lambda *_: {})
    monkeypatch.setattr(ui, 'ColorLivenessWorker', lambda *a, **kw: ColorLivenessWorker(
        *a, **kw, backend_factory=lambda _: analyze))
    dialog = ui.ColorLivenessDialog('123456', '测试员工', camera)
    qtbot.addWidget(dialog)
    repaint = dialog.repaint
    def record_repaint():
        repaint()
        colors.append(dialog._controller.current_color())
    monkeypatch.setattr(dialog, 'repaint', record_repaint)
    acknowledge = dialog._worker.acknowledge_color
    def verify_then_ack(color):
        assert colors[-1] == color
        return acknowledge(color)
    monkeypatch.setattr(dialog._worker, 'acknowledge_color', verify_then_ack)

    try:
        dialog.show()
        qtbot.waitUntil(entered.is_set, timeout=2000)
        earlier = dialog._preview_id
        qtbot.waitUntil(lambda: dialog._preview_id > earlier, timeout=1000)
        assert dialog.preview.pixmap() is not None
        assert '白光有效 0/3' in dialog.message.text() and '已分析 0' in dialog.message.text()
        assert readers == {'color-camera'}
        # 手工请求 Accepted 不能绕过后台门禁；即使推理仍阻塞，也立即关闭。
        dialog.done(QtWidgets.QDialog.Accepted)
        assert not dialog.isVisible() and dialog.result() == QtWidgets.QDialog.Rejected
        assert not dialog.verified and not dialog._worker.stopped()
        assert dialog._controller.current_color() == 'off' and not releases
    finally:
        dialog._shutdown()
        resume.set()
        capture_ended.set()
        qtbot.waitUntil(dialog._worker.stopped)


def test_CT_CLR_07_parent_does_not_read_release_or_quit_before_camera_return(qtbot, monkeypatch):
    from attendance import ui_color_liveness
    from attendance.ui_checkin import CheckInTab
    from attendance import ui_main

    events = []
    window = ui_main.MainWindow.__new__(ui_main.MainWindow)
    QtWidgets.QMainWindow.__init__(window)
    qtbot.addWidget(window)
    widget = window.checkin_tab = CheckInTab(window)
    camera = SimpleNamespace(read=lambda: events.append('read'), release=lambda: events.append('release'),
                             isOpened=lambda: True)
    widget._camera = camera
    widget._timer = SimpleNamespace(stop=lambda: events.append('pause'), start=lambda: events.append('resume'))
    allow_return = Event()
    class Dialog:
        verified = False
        def __init__(self, employee_id, name, capture, parent, *, min_color_ratio):
            assert capture is camera and parent is widget
            assert min_color_ratio == widget.color_liveness_ratio
        def exec_(self):
            return QtWidgets.QDialog.Rejected
        def _shutdown(self):
            return allow_return.is_set()
        def deleteLater(self):
            events.append('delete')
    monkeypatch.setattr(ui_color_liveness, 'ColorLivenessDialog', Dialog)
    monkeypatch.setattr(ui_main, 'close_db', lambda: events.append('close_db'))

    assert not widget._verify_color_liveness(SimpleNamespace(employee_id='123456', name='A'))
    window.show()
    assert not window.close()
    window._on_exit_triggered()
    assert window.isVisible()
    widget._on_timer_tick()
    widget._return_color_camera()
    assert events == ['pause'] and not widget.btn_start.isEnabled()
    allow_return.set()
    qtbot.waitUntil(lambda: widget._color_camera_lease is None)
    assert events == ['pause', 'delete', 'resume'] and widget.btn_start.isEnabled()
    event = QtGui.QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted() and events[-2:] == ['pause', 'release']


@pytest.mark.parametrize('verified,active,expected', [(False,True,False), (True,False,False), (True,True,True)])
def test_CT_CLR_07_only_passed_active_employee_can_confirm(qtbot, monkeypatch, verified, active, expected):
    from attendance import ui_checkin as ui
    widget = ui.CheckInTab()
    qtbot.addWidget(widget)
    assert widget.set_color_liveness_enabled(True)
    assert not widget.set_liveness_enabled(True)
    states = iter((True, active))
    monkeypatch.setattr(ui.EmployeeService, 'get', lambda eid: SimpleNamespace(employee_id=eid, name='A', is_active=next(states)))
    monkeypatch.setattr(widget, '_verify_color_liveness', lambda emp: verified)
    calls = []
    class Confirm:
        recorded = SimpleNamespace(connect=lambda _slot: None)
        def __init__(self, *, parent, employee_id, name):
            calls.append(employee_id)
        def exec_(self):
            return QtWidgets.QDialog.Rejected
    monkeypatch.setattr(ui, 'CheckConfirmDialog', Confirm)
    widget._handle_recognition_name('123456')
    assert calls == (['123456'] if expected else [])
