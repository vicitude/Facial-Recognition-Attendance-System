"""SPEC-002 T-602 改密 UI 测试 (5 个 TC, 与 spec 002 §2.1 Gherkin E-01~E-06 对应).

策略:
- 复用 conftest.py 已有 6 fixture (G-06 红线), 不新增 conftest
- E-01~E-04 mock QMessageBox.warning (避免 offscreen 平台 Qt 段错误, 见 L-005)
- E-01~E-04 mock QDialog.exec_ 走真实 _on_confirm_clicked 路径 (L-005 教训:
  保留内部槽函数调用, fake_exec 走 _on_confirm_clicked + 返 result)
- E-05 mock exec_ 走真实 _on_cancel_clicked
- 每个 TC inline 创建 admin (ensure_default + authenticate), 避免跨文件 fixture 耦合
- MainWindow import 移到 fixture 内部 (避免 collection 阶段触发
  attendance.ui_checkin → recognition → argparse.parse_args() L-002 教训)
"""

import sys

import pytest

pytest.importorskip("PyQt5")

from PyQt5 import QtWidgets

from attendance.services import AdminService
from attendance.ui_change_password import ChangePasswordDialog


# ============================================================
# Session 级 offscreen 平台 + 进程级 sys.argv 保护 (L-002 教训)
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    """offscreen 平台必须在 import QtWidgets 前设 (test_ui_login 同款)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _clean_argv_for_collection():
    """在 collection 阶段保护 sys.argv, 避免 attendance.ui_main import 链
    触发 recognition.py 顶层 parse_args() 时读到 pytest 参数 (L-002 教训).

    Note: conftest._patch_argv 是 function 级, 跑测试函数时才设 sys.argv, 但
    collection 阶段 import 已发生. 这里在 session 启动时立即清 argv, 跑完
    整个 session 才还原. 跨 TC 共享 (不会还原成 pytest 参数), 仅影响
    recognition.parse_args() 的 argv, 不影响 pytest 自身运行.
    """
    original_argv = sys.argv
    sys.argv = [original_argv[0]] if original_argv else [""]
    yield
    sys.argv = original_argv


# ============================================================
# 单例 QApplication + MainWindow factory (避免重复创建)
# ============================================================


@pytest.fixture
def app():
    """单例 QApplication (test_ui_login / test_e2e 同款)."""
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


@pytest.fixture
def make_main_window(app, monkeypatch):
    """工厂函数: 返 (admin) -> MainWindow 实例. 内部 import MainWindow
    避免 collection 阶段触发 recognition.py (L-002 教训).
    """
    from attendance.ui_main import MainWindow

    def _make(admin):
        return MainWindow(admin)
    return _make


# ============================================================
# Helper: mock QDialog.exec_ 走真实槽函数 (L-005 教训)
# ============================================================


def _mock_exec_keeps_slot(monkeypatch, slot_name: str):
    """mock QtWidgets.QDialog.exec_ 走真实 self.<slot_name>() 后返回 result.

    Args:
        monkeypatch: pytest fixture
        slot_name: '_on_confirm_clicked' (E-01~E-04) 或 '_on_cancel_clicked' (E-05)
    """
    def fake_exec(self):
        getattr(self, slot_name)()
        return self.result()
    monkeypatch.setattr(QtWidgets.QDialog, "exec_", fake_exec)


def _mock_warning_noop(monkeypatch):
    """mock QMessageBox.warning 为 no-op + 记录调用, 避免 offscreen 段错误."""
    calls = []
    def fake_warning(*args, **kwargs):
        calls.append((args, kwargs))
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)
    return calls


# ============================================================
# E-01: 改密成功
# ============================================================


def test_TC_ATT_E01_change_password_success(qtbot, monkeypatch, make_main_window):
    """E-01: 旧密码="admin123" + 新密码="newpass456" + 确认匹配
    → AdminService.change_password 真实调用 → dialog accept + statusBar 含"密码已修改".

    覆盖: REQ-E-01 + E-02.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    dlg = ChangePasswordDialog(admin, parent=main)
    # 不 qtbot.addWidget(dlg): monkeypatch 让 main 内部引用此 dlg,
    # self.accept() 后 Qt 会删 C++ 端, teardown 再 close 会 RuntimeError
    # (见 L-005 教训类似场景)

    # 填字段
    dlg.old_password_edit.setText("admin123")
    dlg.new_password_edit.setText("newpass456")
    dlg.confirm_password_edit.setText("newpass456")

    # mock: ChangePasswordDialog 引用 → 返 setup dlg (避免 _on_change_password_triggered 重建)
    monkeypatch.setattr(
        "attendance.ui_main.ChangePasswordDialog",
        lambda *args, **kwargs: dlg,
    )
    # mock: warning no-op + exec_ 走 _on_confirm_clicked
    warning_calls = _mock_warning_noop(monkeypatch)
    _mock_exec_keeps_slot(monkeypatch, "_on_confirm_clicked")

    # 触发完整路径
    main._on_change_password_triggered()

    # 断言: dialog accept + statusBar 提示 + 无 warning + DB 真的改了
    assert dlg.result() == QtWidgets.QDialog.Accepted
    assert "密码已修改" in main.statusBar().currentMessage()
    assert len(warning_calls) == 0
    # DB 侧验证: 用新密码能登录
    fresh = AdminService.authenticate("admin", "newpass456")
    assert fresh.username == "admin"


# ============================================================
# E-02: 旧密码错
# ============================================================


def test_TC_ATT_E02_change_password_old_wrong(qtbot, monkeypatch, make_main_window):
    """E-02: 旧密码="wrong" → QMessageBox.warning AUTH_FAILED + dialog 保持
    + statusBar 不更新.

    覆盖: REQ-E-03.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    dlg = ChangePasswordDialog(admin, parent=main)
    # 不 qtbot.addWidget(dlg): 见 E-01 注释

    initial_status = main.statusBar().currentMessage()

    # 填字段: 旧密码故意错
    dlg.old_password_edit.setText("wrong")
    dlg.new_password_edit.setText("newpass456")
    dlg.confirm_password_edit.setText("newpass456")

    monkeypatch.setattr(
        "attendance.ui_main.ChangePasswordDialog",
        lambda *args, **kwargs: dlg,
    )
    warning_calls = _mock_warning_noop(monkeypatch)
    _mock_exec_keeps_slot(monkeypatch, "_on_confirm_clicked")

    main._on_change_password_triggered()

    # 断言: 弹 1 个 warning, 内容含 AUTH_FAILED, dialog 不 accept, statusBar 不变
    assert len(warning_calls) == 1
    args = warning_calls[0][0]
    assert args[0] is dlg  # parent
    assert args[1] == "修改失败"  # title
    assert "AUTH_FAILED" in args[2]  # message
    assert dlg.result() != QtWidgets.QDialog.Accepted
    assert main.statusBar().currentMessage() == initial_status

    # DB 侧验证: 旧密码仍能登录 (admin123 未改)
    fresh = AdminService.authenticate("admin", "admin123")
    assert fresh.username == "admin"


# ============================================================
# E-03: 新密码 < 6
# ============================================================


def test_TC_ATT_E03_change_password_too_short(qtbot, monkeypatch, make_main_window):
    """E-03: 新密码="123" → QMessageBox.warning PASSWORD_TOO_SHORT + dialog 保持.

    覆盖: REQ-E-04.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    dlg = ChangePasswordDialog(admin, parent=main)
    # 不 qtbot.addWidget(dlg): 见 E-01 注释

    initial_status = main.statusBar().currentMessage()

    dlg.old_password_edit.setText("admin123")
    dlg.new_password_edit.setText("123")
    dlg.confirm_password_edit.setText("123")

    monkeypatch.setattr(
        "attendance.ui_main.ChangePasswordDialog",
        lambda *args, **kwargs: dlg,
    )
    warning_calls = _mock_warning_noop(monkeypatch)
    _mock_exec_keeps_slot(monkeypatch, "_on_confirm_clicked")

    main._on_change_password_triggered()

    # 断言: warning 含 PASSWORD_TOO_SHORT, dialog 不 accept, statusBar 不变
    assert len(warning_calls) == 1
    args = warning_calls[0][0]
    assert args[0] is dlg
    assert args[1] == "修改失败"
    assert "PASSWORD_TOO_SHORT" in args[2]
    assert dlg.result() != QtWidgets.QDialog.Accepted
    assert main.statusBar().currentMessage() == initial_status


# ============================================================
# E-04: 新密码 ≠ 确认新密码
# ============================================================


def test_TC_ATT_E04_change_password_mismatch(qtbot, monkeypatch, make_main_window):
    """E-04: 确认新密码="other789" ≠ 新密码 → warning PASSWORD_MISMATCH + dialog 保持.

    覆盖: REQ-E-05.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    dlg = ChangePasswordDialog(admin, parent=main)
    # 不 qtbot.addWidget(dlg): 见 E-01 注释

    initial_status = main.statusBar().currentMessage()

    dlg.old_password_edit.setText("admin123")
    dlg.new_password_edit.setText("newpass456")
    dlg.confirm_password_edit.setText("other789")

    monkeypatch.setattr(
        "attendance.ui_main.ChangePasswordDialog",
        lambda *args, **kwargs: dlg,
    )
    warning_calls = _mock_warning_noop(monkeypatch)
    _mock_exec_keeps_slot(monkeypatch, "_on_confirm_clicked")

    main._on_change_password_triggered()

    # 断言: warning 含 PASSWORD_MISMATCH, dialog 不 accept, statusBar 不变
    assert len(warning_calls) == 1
    args = warning_calls[0][0]
    assert args[0] is dlg
    assert args[1] == "修改失败"
    assert "PASSWORD_MISMATCH" in args[2]
    assert dlg.result() != QtWidgets.QDialog.Accepted
    assert main.statusBar().currentMessage() == initial_status


# ============================================================
# E-05: 取消
# ============================================================


def test_TC_ATT_E05_change_password_cancel(qtbot, monkeypatch, make_main_window):
    """E-05: 点击取消 → dialog reject + statusBar 不更新 + 不调 change_password.

    覆盖: REQ-E-06.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    dlg = ChangePasswordDialog(admin, parent=main)
    qtbot.addWidget(dlg)

    initial_status = main.statusBar().currentMessage()

    # 不填字段, 直接点取消
    warning_calls = _mock_warning_noop(monkeypatch)
    _mock_exec_keeps_slot(monkeypatch, "_on_cancel_clicked")

    main._on_change_password_triggered()

    # 断言: dialog reject, 不弹 warning, statusBar 不变, DB 未改
    assert dlg.result() == QtWidgets.QDialog.Rejected
    assert len(warning_calls) == 0
    assert main.statusBar().currentMessage() == initial_status
    # DB 侧: 旧密码仍能登录
    fresh = AdminService.authenticate("admin", "admin123")
    assert fresh.username == "admin"
