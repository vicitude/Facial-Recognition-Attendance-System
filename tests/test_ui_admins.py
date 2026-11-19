"""SPEC-002 T-603 管理员管理 UI 测试 (3 个 TC, 与 spec 002 §2.2 Gherkin E-07~E-13 对应).

策略 (沿用 test_ui_change_password.py):
- 复用 conftest.py 已有 6 fixture (G-06 红线), 不新增 conftest
- session 级 offscreen 平台 + sys.argv 保护 (L-002 教训)
- E-07 mock AdminCreateDialog.exec_ 走真实 _on_save_clicked 路径 (L-005 教训:
  保留内部槽函数调用)
- E-08 业务规则按 Gherkin REQ-E-12 (self-delete 优先, count=1 时同样自删保护)
  实现, 弹 SELF_DELETE_FORBIDDEN 而非 LAST_ADMIN_FORBIDDEN
  (与 spec §7 TC 描述 LAST_ADMIN_FORBIDDEN 不一致, 已在 T-603 决策中明确
  业务层 self-delete 优先, 此处按 Gherkin 实施并在测试注释中说明).
- 每个 TC inline 创建 admin (ensure_default + authenticate), 避免跨文件 fixture 耦合
- MainWindow import 移到 fixture 内部 (避免 collection 阶段触发
  attendance.ui_checkin → recognition → argparse.parse_args() L-002 教训)
"""

import sys

import pytest

pytest.importorskip("PyQt5")

from PyQt5 import QtWidgets

from attendance.models import Admin
from attendance.services import AdminService
from attendance.ui_admins import AdminsTab


# ============================================================
# Session 级 offscreen 平台 + 进程级 sys.argv 保护 (L-002 教训)
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    """offscreen 平台必须在 import QtWidgets 前设 (test_ui_login / test_ui_change_password 同款)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def _clean_argv_for_collection():
    """在 collection 阶段保护 sys.argv, 避免 attendance.ui_main import 链
    触发 recognition.py 顶层 parse_args() 时读到 pytest 参数 (L-002 教训).
    """
    original_argv = sys.argv
    sys.argv = [original_argv[0]] if original_argv else [""]
    yield
    sys.argv = original_argv


# ============================================================
# 单例 QApplication + MainWindow factory
# ============================================================


@pytest.fixture
def app():
    """单例 QApplication (test_ui_login / test_ui_change_password / test_e2e 同款)."""
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


@pytest.fixture
def make_main_window(app, qtbot):
    """构造后台并注入签到窗口持有的 CheckInTab；延迟导入避免解析 pytest 参数。"""
    from attendance.ui_kiosk import CheckInWindow
    from attendance.ui_main import MainWindow

    kiosk = CheckInWindow()
    qtbot.addWidget(kiosk)

    def _make(admin):
        return MainWindow(admin, kiosk.checkin_tab)
    return _make


# ============================================================
# Helper: mock QDialog.exec_ 走真实槽函数 (L-005 教训)
# ============================================================


def test_color_ratio_control_defaults_to_85_percent(qtbot, app, monkeypatch):
    tab = AdminsTab.__new__(AdminsTab)
    QtWidgets.QWidget.__init__(tab)
    tab._current_admin = None
    tab._build_ui()
    assert tab.color_ratio_spin.value() == 85
    assert tab.color_ratio_spin.minimum() == 50
    assert tab.color_ratio_spin.maximum() == 100
    tab.deleteLater()


def test_change_registration_code_button_rechecks_current_password(qtbot, app, monkeypatch):
    from attendance.ui_admin_setup import ChangeRegistrationCodeDialog
    from attendance.utils import AuthFailed

    password = 'fixture-password'
    admin = AdminService.create('code-owner', password)
    tab = AdminsTab(admin)
    qtbot.addWidget(tab)
    calls = []
    new_code = 'fixture-new-code'

    def change(admin_id, current_password, code):
        calls.append((admin_id, current_password, code))
        if current_password != password:
            raise AuthFailed('incorrect')

    def exec_dialog(dialog):
        dialog.password_edit.setText('wrong-password')
        dialog.code_edit.setText(new_code)
        dialog.confirmation_edit.setText('does-not-match')
        dialog.save_button.click()
        assert not calls
        dialog.confirmation_edit.setText(new_code)
        dialog.save_button.click()
        assert dialog.result() != QtWidgets.QDialog.Accepted
        assert '不正确' in dialog.error_label.text()
        dialog.password_edit.setText(password)
        dialog.save_button.click()
        assert dialog.password_edit.text() == dialog.code_edit.text() == dialog.confirmation_edit.text() == ''
        return dialog.result()

    monkeypatch.setattr(AdminService, 'change_registration_code', change)
    monkeypatch.setattr(ChangeRegistrationCodeDialog, 'exec_', exec_dialog)
    tab.btn_change_registration_code.click()
    assert calls == [(admin.id, 'wrong-password', new_code), (admin.id, password, new_code)]


def _mock_admin_create_exec(monkeypatch, dialog):
    """mock AdminCreateDialog 实例的 exec_ 走真实 self._on_save_clicked() 后返回 result.

    E-07 用: dialog 已被 setText 好 username / password, _on_save_clicked
    读字段 + 调 AdminService.create + self.accept().

    注意: 不能 monkeypatch 类的 exec_ (AdminCreateDialog 已被前面的 setattr
    替换为 lambda 函数, lambda 无 exec_ 属性, 会 AttributeError).
    改为 monkeypatch dialog 实例的 exec_.
    """
    def fake_exec():
        # 不传 self: monkeypatch.setattr(dialog, ...) 已把 dialog 绑到 self
        dialog._on_save_clicked()
        return dialog.result()
    monkeypatch.setattr(dialog, "exec_", fake_exec)


def _mock_warning_noop(monkeypatch):
    """mock QMessageBox.warning 为 no-op + 记录调用, 避免 offscreen 段错误."""
    calls = []
    def fake_warning(*args, **kwargs):
        calls.append((args, kwargs))
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)
    return calls


def _mock_question_yes(monkeypatch):
    """mock QMessageBox.question 返 Yes (用于删除确认弹窗)."""
    def fake_question(*args, **kwargs):
        return QtWidgets.QMessageBox.Yes
    monkeypatch.setattr(QtWidgets.QMessageBox, "question", fake_question)


# ============================================================
# E-06: 切到索引 2 的页面 + 表格显示 N 行 + 自己行删除按钮禁用
# ============================================================


def test_TC_ATT_E06_admins_tab_shows_list(
    qtbot, monkeypatch, make_main_window,
):
    """E-06: 默认 admin 创建 + 切到 admins tab + 表格行数 == 1
    + 选中自己行 → btn_delete 禁用 (self-delete 保护).

    覆盖: REQ-E-07 + E-13.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)

    # 切到索引 2 的页面 (管理员管理)
    main.tabs.setCurrentWidget(main.admins_tab)
    admins_tab = main.admins_tab

    # 断言: 列名 == ["ID", "用户名", "创建时间"]
    headers = [
        admins_tab.table.horizontalHeaderItem(i).text()
        for i in range(admins_tab.table.columnCount())
    ]
    assert headers == ["ID", "用户名", "创建时间"]

    # 断言: 表格行数 == 1 (只有默认 admin)
    assert admins_tab.table.rowCount() == 1
    # 断言: 单元格内容 (ID + username)
    assert admins_tab.table.item(0, 0).text() == str(admin.id)
    assert admins_tab.table.item(0, 1).text() == "admin"

    # 选中 admin 行 (自己行) → btn_delete 禁用
    admins_tab.table.selectRow(0)
    assert admins_tab._selected_admin_id() == admin.id
    assert admins_tab.btn_delete.isEnabled() is False, (
        "自删保护: 选中自己行时 btn_delete 必须禁用"
    )

    # 取消选中 → btn_delete 禁用 (无目标)
    admins_tab.table.clearSelection()
    assert admins_tab.btn_delete.isEnabled() is False


# ============================================================
# E-07: 创建新管理员成功
# ============================================================


def test_TC_ATT_E07_admins_create_ok(
    qtbot, monkeypatch, make_main_window,
):
    """E-07: 默认 admin + mock AdminCreateDialog.exec_ 填 "200003" / "pass123"
    → 走 _on_save_clicked 真实路径 → AdminService.create("200003", "pass123")
    → 表格行数 + 1, admins 表行数 + 1.

    覆盖: REQ-E-08.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    main.tabs.setCurrentWidget(main.admins_tab)
    admins_tab = main.admins_tab

    # 准备 mock AdminCreateDialog 实例
    from attendance.ui_admins import AdminCreateDialog
    dlg = AdminCreateDialog(parent=admins_tab)
    # 不 qtbot.addWidget(dlg): 见 L-005 教训, mock dialog 走 exec_ 后
    # Qt 端 C++ 对象已删, teardown 再 close 会 RuntimeError
    dlg.username_edit.setText("200003")
    dlg.password_edit.setText("pass123")

    # mock: AdminCreateDialog 引用 → 返 setup 好的 dlg
    monkeypatch.setattr(
        "attendance.ui_admins.AdminCreateDialog",
        lambda *args, **kwargs: dlg,
    )
    # mock: exec_ 走 _on_save_clicked (L-005 教训)
    _mock_admin_create_exec(monkeypatch, dlg)
    # mock: warning no-op (成功路径不弹, 留 hook 防误弹)
    warning_calls = _mock_warning_noop(monkeypatch)

    # 记录初始行数
    initial_row_count = admins_tab.table.rowCount()
    initial_db_count = len(AdminService.list_all())

    # 触发完整路径
    admins_tab._on_create_clicked()

    # 断言: 表格行数 + 1
    assert admins_tab.table.rowCount() == initial_row_count + 1
    # 断言: admins 表行数 + 1
    assert len(AdminService.list_all()) == initial_db_count + 1
    # 断言: 新增行内容
    last_row = admins_tab.table.rowCount() - 1
    assert admins_tab.table.item(last_row, 1).text() == "200003"
    # 断言: 无 warning
    assert len(warning_calls) == 0
    # 断言: dialog accept
    assert dlg.result() == QtWidgets.QDialog.Accepted
    # 断言: statusBar 含"已创建管理员 200003"
    assert "已创建管理员 200003" in main.statusBar().currentMessage()
    # 断言: saved_username 正确
    assert dlg.saved_username == "200003"


# ============================================================
# E-08: 当前 admin 是最后 1 个 + 调 _on_delete + 弹 SELF_DELETE_FORBIDDEN
# ============================================================


def test_TC_ATT_E08_admins_delete_last_forbidden(
    qtbot, monkeypatch, make_main_window,
):
    """E-08: 当前 admin 是最后 1 个 + 选中自己行 + 调 _on_delete_clicked
    → UI 层 self-delete 优先校验 → 弹 SELF_DELETE_FORBIDDEN
    → 表格行数不变 (1).

    业务规则按 Gherkin REQ-E-12 (self-delete 优先, count=1 时同样自删保护):
    即使系统仅剩 1 个 admin, 也走 self-delete 分支而非 LastAdminForbidden.
    (与 spec §7 TC 表格 "关键断言" 列描述一致, 业务层 AdminService.delete
    校验顺序: admin 存在 → self-delete 优先 → LastAdminForbidden).

    覆盖: REQ-E-12 + E-13.
    """
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    main = make_main_window(admin)
    qtbot.addWidget(main)
    main.tabs.setCurrentWidget(main.admins_tab)
    admins_tab = main.admins_tab

    # 确认: 表格仅 1 行 (自己)
    assert admins_tab.table.rowCount() == 1
    assert len(AdminService.list_all()) == 1

    # 选中自己行
    admins_tab.table.selectRow(0)
    assert admins_tab._selected_admin_id() == admin.id
    # 自删保护: btn_delete disabled (即使强行调 _on_delete_clicked 也会被 UI 层拦)
    assert admins_tab.btn_delete.isEnabled() is False

    # mock: warning no-op
    warning_calls = _mock_warning_noop(monkeypatch)
    # 不需要 mock question: self-delete 优先, 走不到确认弹窗

    # 触发 _on_delete_clicked (绕过 btn_delete disabled, 模拟用户强制场景)
    admins_tab._on_delete_clicked()

    # 断言: 弹 1 个 warning, 标题"删除失败", 内容含 SELF_DELETE_FORBIDDEN
    assert len(warning_calls) == 1
    args = warning_calls[0][0]
    assert args[0] is admins_tab  # parent
    assert args[1] == "删除失败"
    assert "SELF_DELETE_FORBIDDEN" in args[2]
    assert f"不能删除当前登录的管理员 {admin.id}" in args[2]

    # 断言: 表格行数不变 (1)
    assert admins_tab.table.rowCount() == 1
    # 断言: admins 表行数不变
    assert len(AdminService.list_all()) == 1
    # 断言: admin 仍在表里
    assert Admin.get_by_id(admin.id).username == "admin"
    # 断言: statusBar 未更新 (操作失败, 不提示成功信息)
    assert "已删除" not in main.statusBar().currentMessage()
