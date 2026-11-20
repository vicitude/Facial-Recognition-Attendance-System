import sys
from types import SimpleNamespace

from PyQt5 import QtWidgets


def test_CT_CLR_13_diagnostics_visible_in_admin(qtbot, monkeypatch, tmp_path):
    from attendance import color_failure_log
    monkeypatch.setattr(color_failure_log, '_LOG_PATH', tmp_path / 'failures.jsonl')
    monkeypatch.setattr(sys, 'argv', sys.argv[:1])
    from attendance import ui_main, ui_color_liveness, ui_admins
    from attendance.ui_checkin import CheckInTab
    from attendance.color_light_liveness import ColorResult

    for name in ('EmployeesTab', 'RecordsTab', 'SchedulesTab'):
        monkeypatch.setattr(ui_main, name, QtWidgets.QWidget)
    monkeypatch.setattr(ui_admins.AdminsTab, '_refresh_table', lambda self: None)
    tab = CheckInTab()
    qtbot.addWidget(tab)
    admin = SimpleNamespace(username='tester', is_super=True)
    window = ui_main.MainWindow(admin, tab)
    qtbot.addWidget(window)
    label = window.admins_tab.color_diagnostics_label
    assert label.text() == '暂无彩光诊断'
    row = dict(cycle=1, color='green', samples=2, hits=1, motion_skips=1,
               quality_skips={'blurry': 3}, delta_median=.0375, delta_peak=.09)
    result = ColorResult('rejected', 'rejected', 'green', 0, 2, 'COLOR_SAMPLES_INSUFFICIENT',
                         dict(color_diagnostics=[row]))
    dialog = ui_color_liveness.ColorLivenessDialog
    monkeypatch.setattr(ui_color_liveness, 'load_or_create_key', lambda _: b'')
    monkeypatch.setattr(ui_color_liveness.FaceTemplateService, 'load_employee_vectors', lambda *_: {})
    monkeypatch.setattr(ui_color_liveness, 'ColorLivenessWorker', lambda *a, **kw: SimpleNamespace(
        stop=lambda: True, snapshot=lambda: {'result': result}))
    monkeypatch.setattr(dialog, 'exec_', lambda self: QtWidgets.QDialog.Rejected)
    tab._camera = SimpleNamespace(release=lambda: None)
    assert not tab._verify_color_liveness(SimpleNamespace(employee_id='123456', name='test-person'))
    for fragment in ('COLOR_SAMPLES_INSUFFICIENT', '85%', '第1轮 绿光', '有效 2', '达标 1',
                     '位移丢弃 1', '模糊 3', '+3.75 个百分点', '+9.00 个百分点'):
        assert fragment in label.text()
    assert '123456' not in label.text() and 'test-person' not in label.text()
    reopened = ui_main.MainWindow(admin, tab)
    qtbot.addWidget(reopened)
    assert reopened.admins_tab.color_diagnostics_label.text() == label.text()
