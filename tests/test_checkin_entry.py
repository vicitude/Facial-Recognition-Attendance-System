"""SPEC-012：无需 conftest、MySQL 或相机的签到入口验收。"""

import logging
import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PyQt5 import QtCore, QtGui, QtTest, QtWidgets, sip


@pytest.fixture
def ui(monkeypatch):
    import cv2
    import peewee
    import pymysql

    db_connect = Mock(side_effect=AssertionError('不允许连接真实数据库'))
    db_sql = Mock(side_effect=AssertionError('不允许执行真实 SQL'))
    capture = Mock(side_effect=AssertionError('必须使用模拟相机'))
    monkeypatch.setattr(pymysql, 'connect', db_connect)
    monkeypatch.setattr(peewee.MySQLDatabase, 'execute_sql', db_sql)
    monkeypatch.setattr(cv2, 'VideoCapture', capture)

    # 旧识别模块在导入时解析命令行并加载模型，不属于入口验收范围。
    recognition = ModuleType('recognition')
    recognition.recognition = Mock(side_effect=AssertionError('不应运行识别'))
    monkeypatch.setitem(sys.modules, 'recognition', recognition)
    logger = logging.getLogger('attendance')
    null_handler = logging.NullHandler()
    logger.addHandler(null_handler)
    try:
        from attendance import db, services, ui_checkin, ui_kiosk, ui_login
        from attendance.utils import AuthFailed, InternalError
    finally:
        logger.removeHandler(null_handler)

    for service, method in (
        (services.AdminService, 'list_all'),
        (services.EmployeeService, 'list_all'),
        (services.CheckService, 'list_records'),
        (services.ScheduleService, 'list_all'),
    ):
        monkeypatch.setattr(service, method, lambda *args, **kwargs: [])
    authenticate = Mock(side_effect=AuthFailed('测试认证未通过'))
    show_error = Mock()
    close_db = Mock()
    monkeypatch.setattr(services.AdminService, 'authenticate', authenticate)
    monkeypatch.setattr(ui_login, 'show_error', show_error)
    monkeypatch.setattr(db, 'close_db', close_db)
    yield SimpleNamespace(
        kiosk=ui_kiosk, login=ui_login, checkin=ui_checkin, services=services,
        capture=capture, authenticate=authenticate, show_error=show_error,
        close_db=close_db, InternalError=InternalError,
    )
    db_connect.assert_not_called()
    db_sql.assert_not_called()
    recognition.recognition.assert_not_called()


@pytest.fixture
def app():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _flush_deletes():
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    QtWidgets.QApplication.processEvents()


@pytest.fixture
def window(ui, app):
    kiosk = ui.kiosk.CheckInWindow()
    kiosk.show()
    try:
        yield kiosk
    finally:
        # 中途断言失败时也先销毁后台，避免签到窗口拒绝关闭。
        admin = kiosk._admin_window
        if admin is not None and not sip.isdeleted(admin):
            admin.close()
            _flush_deletes()
        kiosk.checkin_tab._color_camera_lease = None
        kiosk.close()
        kiosk.deleteLater()
        _flush_deletes()


@pytest.mark.parametrize('work_area', [
    QtCore.QRect(30, 20, 1280, 650),
    QtCore.QRect(-1024, 40, 1024, 390),
])
def test_TC_ENTRY_003_compact_window(monkeypatch, ui, window, work_area):
    screen = SimpleNamespace(availableGeometry=lambda: work_area)
    monkeypatch.setattr(QtWidgets.QApplication, 'screenAt', lambda _: screen)
    window._fit_startup_geometry()
    QtWidgets.QApplication.processEvents()
    assert work_area.contains(window.frameGeometry())

    scroll = window._content_scroll
    bar = scroll.verticalScrollBar()
    if work_area.height() < 400:
        assert bar.maximum() > 0
    tips = next(label for label in window.checkin_tab.findChildren(QtWidgets.QLabel)
                if '下一位请重新开始识别' in label.text())
    for control in (window.checkin_tab.btn_open, window.checkin_tab.btn_start,
                    window.checkin_tab.btn_stop, tips):
        scroll.ensureWidgetVisible(control, 0, 0)
        bounds = QtCore.QRect(control.mapTo(scroll.viewport(), QtCore.QPoint()), control.size())
        assert scroll.viewport().rect().contains(bounds)
    assert window.settings_button.isVisibleTo(window)


def _drive_login(monkeypatch, ui, interact):
    """在真实模态循环中操作对话框；断言失败或未关闭也能退出循环。"""
    original_exec = ui.login.LoginDialog.exec_
    dialogs = []
    results = []
    errors = []

    def exec_dialog(dialog):
        dialogs.append(dialog)

        def act():
            try:
                assert QtWidgets.QApplication.activeModalWidget() is dialog
                assert dialog.windowTitle() == '管理员登录'
                interact(dialog)
            except Exception as exc:
                errors.append(exc)
            finally:
                if dialog.isVisible():
                    dialog.reject()

        QtCore.QTimer.singleShot(0, act)
        results.append(original_exec(dialog))
        return results[-1]

    monkeypatch.setattr(ui.login.LoginDialog, 'exec_', exec_dialog)

    def verify():
        if errors:
            raise errors[0]
        return dialogs, results

    return verify


@pytest.mark.parametrize('default_admin_fails', [False, True], ids=['startup', 'cleanup-on-failure'])
def test_TC_ENTRY_001(monkeypatch, ui, app, default_admin_fails):
    import attendance_ui as entry

    config = {'admin': {'default_username': 'fixture-admin', 'default_password': 'fixture-secret'}}
    calls = Mock()
    calls.load.return_value = config
    if default_admin_fails:
        calls.ensure_default.side_effect = ui.InternalError('测试初始化失败')
    monkeypatch.setattr(entry.ConfigService, 'load', calls.load)
    monkeypatch.setattr(entry, 'init_db', calls.init_db)
    monkeypatch.setattr(entry.AdminService, 'ensure_default', calls.ensure_default)
    monkeypatch.setattr(entry, 'close_db', calls.close_db)
    monkeypatch.setattr(entry, '_critical', calls.critical)
    login = Mock(return_value=QtWidgets.QDialog.Rejected)
    monkeypatch.setattr(ui.login.LoginDialog, 'exec_', login)
    windows = []
    make_kiosk = entry.CheckInWindow

    def create_window():
        calls.create_kiosk()
        windows.append(make_kiosk())
        return windows[-1]

    def run_loop():
        calls.event_loop()
        assert len(windows) == 1
        kiosk = windows[0]
        assert kiosk.isVisible()
        assert [w for w in app.topLevelWidgets() if w.isVisible()] == [kiosk]
        assert kiosk.windowTitle() == '实时签到'
        assert kiosk.settings_button.accessibleName() == '管理员设置'
        assert kiosk.settings_button.toolTip() == '管理员设置'
        tab = kiosk.checkin_tab
        assert kiosk.findChildren(ui.checkin.CheckInTab) == [tab]
        assert tab.isVisible()
        assert tab._camera is None
        assert not tab.flag_recognition
        assert not tab.btn_start.isEnabled()
        assert not kiosk.findChildren(ui.login.LoginDialog)
        return 17

    monkeypatch.setattr(entry, 'CheckInWindow', create_window)
    monkeypatch.setattr(entry, '_application', lambda: SimpleNamespace(exec_=run_loop))
    try:
        assert entry.main() == (1 if default_admin_fails else 17)
        assert calls.mock_calls[:3] == [
            call.load(), call.init_db(config), call.ensure_default('fixture-admin', 'fixture-secret'),
        ]
        if default_admin_fails:
            calls.critical.assert_called_once()
            assert calls.mock_calls[-1] == call.close_db()
            assert not windows
            calls.event_loop.assert_not_called()
        else:
            calls.critical.assert_not_called()
            assert calls.mock_calls[3:] == [call.create_kiosk(), call.event_loop(), call.close_db()]
        calls.close_db.assert_called_once_with()
        login.assert_not_called()
        ui.authenticate.assert_not_called()
        ui.capture.assert_not_called()
    finally:
        for kiosk in windows:
            kiosk.close()
            kiosk.deleteLater()
        _flush_deletes()


@pytest.mark.parametrize('operation', ['settings', 'close'])
@pytest.mark.parametrize('leased', [False, True], ids=['release', 'busy'])
def test_TC_ENTRY_002(monkeypatch, ui, window, operation, leased):
    events = []
    camera = SimpleNamespace(
        isOpened=lambda: True,
        read=lambda: (False, None),
        release=Mock(side_effect=lambda: events.append('release')),
    )
    ui.capture.side_effect = None
    ui.capture.return_value = camera
    tab = window.checkin_tab
    tab.btn_open.click()
    ui.capture.assert_called_once()
    assert tab._camera is camera
    if leased:
        tab._color_camera_lease = object()

    login_factory = Mock(wraps=ui.login.LoginDialog)
    monkeypatch.setattr(ui.kiosk, 'LoginDialog', login_factory)

    def cancel(dialog):
        events.append('login')
        assert tab._camera is None
        dialog.cancel_button.click()

    verify_login = _drive_login(monkeypatch, ui, cancel)
    if operation == 'settings':
        window.settings_button.click()
    else:
        assert window.close() is not leased
    dialogs, results = verify_login()

    if leased:
        assert window.isVisible()
        assert tab._camera is camera
        assert '彩光后台正在归还摄像头' in window.statusBar().currentMessage()
        camera.release.assert_not_called()
        login_factory.assert_not_called()
        assert not events
    else:
        camera.release.assert_called_once_with()
        assert tab._camera is None
        if operation == 'settings':
            login_factory.assert_called_once_with(window)
            assert len(dialogs) == 1
            assert results == [QtWidgets.QDialog.Rejected]
            assert events == ['release', 'login']
            assert window.isVisible()
        else:
            login_factory.assert_not_called()
            assert events == ['release']
            assert not window.isVisible()
    assert window._admin_window is None
    ui.authenticate.assert_not_called()
    ui.capture.assert_called_once()


@pytest.mark.parametrize('outcome', [
    'cancel', 'escape', 'close', 'empty-username', 'empty-password',
    'bad-password', 'accepted-without-admin',
])
def test_PT_ENTRY_101(monkeypatch, ui, window, outcome):
    make_admin = Mock(wraps=ui.kiosk.MainWindow)
    monkeypatch.setattr(ui.kiosk, 'MainWindow', make_admin)
    tab = window.checkin_tab

    def interact(dialog):
        dialog.username_edit.setText('   ' if outcome == 'empty-username' else '  fixture-admin  ')
        dialog.password_edit.setText('' if outcome == 'empty-password' else ' wrong password ')
        if outcome == 'cancel':
            dialog.cancel_button.click()
        elif outcome == 'escape':
            QtTest.QTest.keyClick(dialog, QtCore.Qt.Key_Escape)
        elif outcome == 'close':
            assert dialog.close()
        elif outcome == 'accepted-without-admin':
            dialog.accept()
        else:
            dialog.login_button.click()
            assert dialog.isVisible(), '验证失败必须留在登录框'
            assert dialog.admin is None
            assert ui.show_error.call_args.args[1] == 'AUTH_FAILED'
            make_admin.assert_not_called()
            dialog.cancel_button.click()
        assert not dialog.isVisible(), '登录框必须由被测操作关闭'

    verify_login = _drive_login(monkeypatch, ui, interact)
    window.settings_button.click()
    dialogs, results = verify_login()
    expected = QtWidgets.QDialog.Accepted if outcome == 'accepted-without-admin' else QtWidgets.QDialog.Rejected
    assert results == [expected]
    assert dialogs[0].password_edit.text() == ''
    make_admin.assert_not_called()
    assert window._admin_window is None
    assert window.isVisible() and window.settings_button.isEnabled()
    assert window.checkin_tab is tab and tab.btn_open.isEnabled()
    if outcome == 'bad-password':
        ui.authenticate.assert_called_once_with('fixture-admin', ' wrong password ')
    else:
        ui.authenticate.assert_not_called()
    if outcome in ('empty-username', 'empty-password', 'bad-password'):
        ui.show_error.assert_called_once()
    else:
        ui.show_error.assert_not_called()
    ui.capture.assert_not_called()
    ui.close_db.assert_not_called()
    _flush_deletes()
    assert sip.isdeleted(dialogs[0])


@pytest.mark.parametrize('exit_via', ['button', 'menu', 'window-close'])
def test_PT_ENTRY_102(monkeypatch, ui, window, app, exit_via):
    tab = window.checkin_tab
    ui.authenticate.side_effect = None
    ui.authenticate.return_value = SimpleNamespace(id=1, username='fixture-admin')
    quit_app = Mock()
    monkeypatch.setattr(app, 'quit', quit_app)
    monkeypatch.setattr(QtWidgets.QApplication, 'quit', quit_app)

    def log_in(dialog):
        dialog.username_edit.setText('  fixture-admin  ')
        dialog.password_edit.setText(' fixture-secret ')
        dialog.login_button.click()
        assert not dialog.isVisible() and dialog.admin is ui.authenticate.return_value

    verify_login = _drive_login(monkeypatch, ui, log_in)
    window.settings_button.click()
    dialogs, results = verify_login()
    assert results == [QtWidgets.QDialog.Accepted]
    ui.authenticate.assert_called_once_with('fixture-admin', ' fixture-secret ')
    first_login = dialogs[0]
    _flush_deletes()

    admin = window._admin_window
    assert admin is not None and admin.isVisible()
    assert admin.isWindow() and admin.parentWidget() is window
    assert admin.windowModality() == QtCore.Qt.WindowModal
    assert admin.checkin_tab is tab and tab.window() is window
    assert window.findChildren(ui.checkin.CheckInTab) == [tab]
    assert not admin.findChildren(ui.checkin.CheckInTab)
    assert [admin.tabs.tabText(i) for i in range(admin.tabs.count())] == [
        '人员管理', '打卡记录', '管理员管理', '班次管理',
    ]
    assert admin.tabs.currentWidget() is admin.employees_tab
    assert not window.close(), '后台仍打开时不得关闭签到窗口'
    assert admin.action_exit.shortcut() == QtGui.QKeySequence('Ctrl+Q')
    if exit_via == 'button':
        admin.exit_button.click()
    elif exit_via == 'menu':
        admin.action_exit.trigger()
    else:
        assert admin.close()
    _flush_deletes()

    assert sip.isdeleted(admin)
    assert window._admin_window is None
    assert window.isVisible() and window.checkin_tab is tab
    assert window.settings_button.isEnabled() and tab.btn_open.isEnabled()
    quit_app.assert_not_called()
    ui.close_db.assert_not_called()

    def cancel_fresh_login(dialog):
        assert dialog is not first_login
        assert dialog.admin is None
        assert dialog.username_edit.text() == ''
        assert dialog.password_edit.text() == ''
        dialog.cancel_button.click()
        assert not dialog.isVisible()

    verify_login = _drive_login(monkeypatch, ui, cancel_fresh_login)
    window.settings_button.click()
    assert verify_login()[1] == [QtWidgets.QDialog.Rejected]
    ui.authenticate.assert_called_once()
    assert window._admin_window is None
    assert window.isVisible()
    ui.capture.assert_not_called()
