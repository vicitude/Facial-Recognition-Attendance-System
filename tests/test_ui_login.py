"""SPEC-001-C 阶段 1 骨架烟测: 仅覆盖登录 4 个 TC (C01~C04).

阶段 2 补 C05~C15 (3 个 Tab), 阶段 3 补 C16~C18 (RecordsTab).
全部用 pytest-qt + offscreen 平台, 不依赖真实显示器.
"""

import sys

import pytest

pytest.importorskip("PyQt5")


# offscreen 平台必须在 import QtWidgets 前设
@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    from PyQt5 import QtWidgets
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield a


@pytest.fixture(autouse=True)
def _patch_sys_exit(monkeypatch):
    """LoginDialog.closeEvent 会调 sys.exit(0) 杀掉 pytest 进程,
    这里改成 raise SystemExit, 让 C-04 用 pytest.raises 验证."""
    def fake_exit(code=0):
        raise SystemExit(code)
    monkeypatch.setattr(sys, "exit", fake_exit)


# ============================================================
# TC-ATT-C01 / C02 / C03 / C04
# ============================================================


def test_TC_ATT_C01_login_dialog_launches(app):
    """C-01: LoginDialog 标题 + 密码框 echoMode == Password."""
    from attendance.ui_login import LoginDialog
    from attendance.services import AdminService

    AdminService.ensure_default("admin", "admin123")

    dlg = LoginDialog()
    assert dlg.windowTitle() == "签到系统 v1.0.0"
    assert dlg.password_edit.echoMode() == dlg.password_edit.Password


def test_TC_ATT_C02_login_success_enters_main(app):
    """C-02: 输入正确账号 → accept() + admin 已赋值."""
    from attendance.ui_login import LoginDialog
    from attendance.services import AdminService

    AdminService.ensure_default("admin", "admin123")

    dlg = LoginDialog()
    dlg.username_edit.setText("admin")
    dlg.password_edit.setText("admin123")
    dlg._on_login_clicked()
    assert dlg.result() == dlg.Accepted
    assert dlg.admin is not None
    assert dlg.admin.username == "admin"


def test_TC_ATT_C03_login_failed_shows_warning(app, monkeypatch):
    """C-03: 输入错密码 → QMessageBox.warning 含 AUTH_FAILED, dialog 仍保持."""
    from PyQt5 import QtWidgets
    from attendance.ui_login import LoginDialog
    from attendance.services import AdminService

    AdminService.ensure_default("admin", "admin123")

    captured: dict = {}
    def fake_warning(parent, title, text, *args, **kwargs):
        captured["title"] = title
        captured["text"] = text
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(fake_warning))

    dlg = LoginDialog()
    dlg.username_edit.setText("admin")
    dlg.password_edit.setText("wrongpass")
    dlg._on_login_clicked()
    assert captured["title"] == "登录失败"
    assert "AUTH_FAILED" in captured["text"]
    assert dlg.result() != dlg.Accepted


def test_TC_ATT_C04_login_close_triggers_exit(app):
    """C-04: LoginDialog 的 closeEvent 触发 sys.exit(0) → SystemExit(0).

    注: offscreen 平台下 dlg.close() 不触发 closeEvent (Qt 已知行为),
    这里直接调 closeEvent, 测的是 closeEvent → sys.exit 的契约.
    """
    from PyQt5 import QtGui
    from attendance.ui_login import LoginDialog
    from attendance.services import AdminService

    AdminService.ensure_default("admin", "admin123")

    dlg = LoginDialog()
    event = QtGui.QCloseEvent()
    with pytest.raises(SystemExit) as exc_info:
        dlg.closeEvent(event)
    assert exc_info.value.code == 0
