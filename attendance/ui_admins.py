"""签到/签退人员管理系统 - 管理员管理 Tab (SPEC-002 §3.3 AdminsTab / AdminCreateDialog).

T-603 产出物:
- AdminsTab: 表格 + 工具栏 (新增/删除/刷新) + 自删保护 (选中自己行 → btn_delete 禁用)
- AdminCreateDialog: 2 输入控件 (username/password) + 保存/取消

设计决策:
- 弹窗直接走 QMessageBox.warning, 不依赖 ui_utils.show_error, 避免修改既有
  _TITLE_MAP (沿用 ui_change_password.py 模式, 见 AGENTS.md §5 红线).
- admin_id 存 item.data(Qt.UserRole), 不单独占一列, 渲染与查询解耦.
- 自删保护 (E06/E13 验证): 选中自己行 → btn_delete.setEnabled(False),
  业务层 AdminService.delete 仍然走 self-delete 优先校验 (Gherkin REQ-E-12,
  count=1 时同样自删保护, 不走 LastAdminForbidden).
- 状态栏回调: self.window().statusBar() (Qt 标准做法, 不耦合 MainWindow).
"""

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from attendance.models import Admin
from attendance.services import AdminService
from attendance.ui_admin_setup import ChangeRegistrationCodeDialog
from attendance.ui_theme import card, configure_table, label, page_header, prepare_dialog
from attendance.utils import (
    AdminNotFound,
    InternalError,
    LastAdminForbidden,
    PasswordTooShort,
    SelfDeleteForbidden,
    UsernameExists,
)


# 异常类 → 错误码 映射 (SPEC-002 §6.1)
_EXC_TO_ERROR_CODE: dict[str, str] = {
    "UsernameExists": "USERNAME_EXISTS",
    "PasswordTooShort": "PASSWORD_TOO_SHORT",
    "LastAdminForbidden": "LAST_ADMIN_FORBIDDEN",
    "SelfDeleteForbidden": "SELF_DELETE_FORBIDDEN",
    "AdminNotFound": "ADMIN_NOT_FOUND",
    "InternalError": "INTERNAL_ERROR",  # USERNAME_TOO_LONG 走这里
}


# 错误码 → 弹窗标题 映射 (SPEC-002 §6.1, 沿用 ui_change_password.py 内联模式)
_TITLE_MAP: dict[str, str] = {
    "USERNAME_EXISTS": "创建失败",
    "USERNAME_TOO_LONG": "创建失败",
    "PASSWORD_TOO_SHORT": "创建失败",
    "LAST_ADMIN_FORBIDDEN": "删除失败",
    "SELF_DELETE_FORBIDDEN": "删除失败",
    "ADMIN_NOT_FOUND": "删除失败",
    "INTERNAL_ERROR": "创建失败",
}


def _show_admin_error(
    parent: QtWidgets.QWidget,
    error_code: str,
    message: str,
) -> None:
    """AdminsTab 专用: 弹 QMessageBox.warning, 标题按 _TITLE_MAP 决定.

    不走 ui_utils.show_error (避免修改既有 _TITLE_MAP, AGENTS.md §5 红线).
    """
    title = _TITLE_MAP.get(error_code, "操作失败")
    QtWidgets.QMessageBox.warning(parent, title, message)


class AdminsTab(QtWidgets.QWidget):
    """管理员管理 Tab - 表格 + 工具栏.

    列: ID / 用户名 / 创建时间 (3 列, ID 仅作展示, admin_id 存 item.data(Qt.UserRole)).
    """

    liveness_requested = QtCore.pyqtSignal(bool)
    color_liveness_requested = QtCore.pyqtSignal(bool)
    color_liveness_ratio_changed = QtCore.pyqtSignal(float)
    COLUMNS: list = ["ID", "用户名", "创建时间"]

    def __init__(
        self,
        current_admin: Admin,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._current_admin = current_admin
        self._build_ui()
        self._wire_signals()
        self._refresh_table()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        self.admin_summary = label('共 0 个账号', 'badge')
        header = page_header('管理员管理', '创建和维护可以登录本地系统的管理员账号。')
        header.layout().addWidget(self.admin_summary)
        layout.addWidget(header)

        settings_card = card()
        settings_layout = QtWidgets.QHBoxLayout(settings_card)
        settings_layout.setContentsMargins(20, 16, 20, 16)
        settings_text = QtWidgets.QVBoxLayout()
        settings_text.addWidget(label('活体验证设置', 'sectionTitle'))
        settings_text.addWidget(label('三次眨眼或彩色光验证；切换前请关闭相机，重启后默认关闭。'))
        self.btn_color_liveness = QtWidgets.QPushButton('彩色光试运行：关闭')
        self.btn_color_liveness.setCheckable(True)
        self.btn_color_liveness.setChecked(False)
        self.btn_color_liveness.setStyleSheet('QPushButton { border-radius: 22px; min-height: 24px; padding: 10px 22px; }')
        self.btn_color_liveness.setAccessibleName('彩色光试运行开关')
        self.color_ratio_spin = QtWidgets.QDoubleSpinBox()
        self.color_ratio_spin.setRange(50, 100)
        self.color_ratio_spin.setSingleStep(5)
        self.color_ratio_spin.setDecimals(0)
        self.color_ratio_spin.setValue(85)
        self.color_ratio_spin.setSuffix('%')
        self.color_ratio_spin.setAccessibleName('彩光合格帧比例')
        ratio_layout = QtWidgets.QHBoxLayout()
        ratio_layout.addWidget(QtWidgets.QLabel('合格帧比例'))
        ratio_layout.addWidget(self.color_ratio_spin)
        settings_text.addLayout(ratio_layout)
        settings_layout.addLayout(settings_text, 1)
        self.btn_liveness = QtWidgets.QPushButton('活体试运行：关闭')
        self.btn_liveness.setCheckable(True)
        self.btn_liveness.setChecked(False)
        self.btn_liveness.setStyleSheet(
            'QPushButton { border-radius: 22px; min-height: 24px; padding: 10px 22px; }'
            'QPushButton:checked { background: #7c83e8; color: white; border-color: #7c83e8; }'
        )
        self.btn_liveness.setAccessibleName('活体试运行开关')
        settings_layout.addWidget(self.btn_liveness)
        settings_layout.addWidget(self.btn_color_liveness)
        diagnostics = QtWidgets.QGroupBox('最近一次彩光诊断')
        diagnostics_layout = QtWidgets.QVBoxLayout(diagnostics)
        self.color_diagnostics_label = QtWidgets.QLabel('暂无彩光诊断')
        self.color_diagnostics_label.setTextFormat(QtCore.Qt.PlainText)
        self.color_diagnostics_label.setWordWrap(True)
        self.color_diagnostics_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        diagnostics_layout.addWidget(self.color_diagnostics_label)
        settings_layout.addWidget(diagnostics)
        layout.addWidget(settings_card)

        # 工具栏
        toolbar = QtWidgets.QHBoxLayout()
        toolbar_card = card()
        toolbar_card_layout = QtWidgets.QHBoxLayout(toolbar_card)
        toolbar_card_layout.setContentsMargins(16, 12, 16, 12)
        self.btn_add = QtWidgets.QPushButton("新增")
        self.btn_delete = QtWidgets.QPushButton("删除")
        self.btn_refresh = QtWidgets.QPushButton("刷新")
        self.btn_add.setObjectName('primary')
        self.btn_delete.setObjectName('danger')
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch(1)
        self.btn_change_registration_code = QtWidgets.QPushButton('更换设置码')
        self.btn_change_registration_code.setEnabled(bool(self._current_admin and self._current_admin.is_super))
        toolbar.addWidget(self.btn_change_registration_code)
        toolbar_card_layout.addLayout(toolbar)
        layout.addWidget(toolbar_card)

        # 表格
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.table.verticalHeader().setVisible(False)
        configure_table(self.table)
        layout.addWidget(self.table)

        # 初始: 无选中 → btn_delete 禁用
        self.btn_delete.setEnabled(False)

    def set_liveness_state(self, enabled: bool) -> None:
        """同步旧活体实际状态，不触发新的切换请求。"""
        previous = self.btn_liveness.blockSignals(True)
        self.btn_liveness.setChecked(bool(enabled))
        self.btn_liveness.setText('活体试运行：开启' if enabled else '活体试运行：关闭')
        self.btn_liveness.blockSignals(previous)

    @QtCore.pyqtSlot(str)
    def set_color_diagnostics(self, text: str) -> None:
        self.color_diagnostics_label.setText(text or '暂无彩光诊断')

    def set_color_liveness_state(self, enabled: bool) -> None:
        previous = self.btn_color_liveness.blockSignals(True)
        self.btn_color_liveness.setChecked(bool(enabled))
        self.btn_color_liveness.setText('彩色光试运行：开启' if enabled else '彩色光试运行：关闭')
        self.btn_color_liveness.blockSignals(previous)

    def _wire_signals(self) -> None:
        self.btn_liveness.clicked.connect(self.liveness_requested.emit)
        self.btn_color_liveness.clicked.connect(self.color_liveness_requested.emit)
        self.color_ratio_spin.valueChanged.connect(lambda value: self.color_liveness_ratio_changed.emit(value / 100.0))
        self.btn_add.clicked.connect(self._on_create_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_refresh.clicked.connect(self._refresh_table)
        self.btn_change_registration_code.clicked.connect(self._on_change_registration_code)
        # 选中变化时, 动态启用/禁用 btn_delete (自删保护)
        self.table.itemSelectionChanged.connect(
            self._on_selection_changed
        )

    # ----------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------

    def _on_change_registration_code(self) -> None:
        dialog = ChangeRegistrationCodeDialog(self._current_admin.id, self)
        try:
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self._show_status('设置码已更换')
        finally:
            dialog.deleteLater()

    def _selected_admin_id(self) -> Optional[int]:
        """返回当前选中行的 admin_id (从 item.data(Qt.UserRole) 读), 无选中返 None."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return item.data(QtCore.Qt.UserRole)

    def _selected_username(self) -> str:
        """返回当前选中行的 username (用于确认弹窗内容)."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return ""
        item = self.table.item(rows[0].row(), 1)
        return item.text() if item else ""

    def _refresh_table(self) -> None:
        """调 AdminService.list_all() 渲染表格 + 触发自删保护重算."""
        try:
            admins = AdminService.list_all()
        except Exception as e:
            _show_admin_error(
                self, "INTERNAL_ERROR",
                f"加载管理员列表失败: {e} (错误码: INTERNAL_ERROR)",
            )
            return
        self.table.setRowCount(len(admins))
        self.admin_summary.setText(f'共 {len(admins)} 个账号')
        for r, admin in enumerate(admins):
            id_item = QtWidgets.QTableWidgetItem(str(admin.id))
            id_item.setData(QtCore.Qt.UserRole, admin.id)
            self.table.setItem(r, 0, id_item)
            self.table.setItem(
                r, 1, QtWidgets.QTableWidgetItem(admin.username or ""),
            )
            created = (
                admin.created_at.strftime("%Y-%m-%d %H:%M:%S")
                if admin.created_at else ""
            )
            self.table.setItem(
                r, 2, QtWidgets.QTableWidgetItem(created),
            )
        # 重新触发自删保护 (避免上次选中的残留)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        """选中行变化时: 自己行 → 禁用 btn_delete; 他人行 → 启用."""
        target_id = self._selected_admin_id()
        self.btn_delete.setEnabled(
            target_id is not None and target_id != self._current_admin.id
        )

    def _show_status(self, message: str) -> None:
        """通过顶层 window().statusBar() 显示状态 (解耦 MainWindow)."""
        window = self.window()
        if isinstance(window, QtWidgets.QMainWindow):
            window.statusBar().showMessage(message, 5000)

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _on_create_clicked(self) -> None:
        dlg = AdminCreateDialog(parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._refresh_table()
            username = dlg.saved_username or ""
            if username:
                self._show_status(f"已创建管理员 {username}")

    def _on_delete_clicked(self) -> None:
        target_id = self._selected_admin_id()
        if target_id is None:
            _show_admin_error(
                self, "ADMIN_NOT_FOUND",
                "请先选中一行管理员 (错误码: ADMIN_NOT_FOUND)",
            )
            return
        # UI 层自删保护 (前置, 避免弹无意义确认框)
        # 业务层 AdminService.delete 仍会再校验一次 (Gherkin REQ-E-12 self-delete 优先)
        if target_id == self._current_admin.id:
            _show_admin_error(
                self, "SELF_DELETE_FORBIDDEN",
                f"不能删除当前登录的管理员 {target_id} "
                "(错误码: SELF_DELETE_FORBIDDEN)",
            )
            return
        username = self._selected_username()
        reply = QtWidgets.QMessageBox.question(
            self, "确认删除", f"确认删除管理员 {username}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            AdminService.delete(
                admin_id=target_id,
                current_admin_id=self._current_admin.id,
            )
        except (
            SelfDeleteForbidden,
            LastAdminForbidden,
            AdminNotFound,
        ) as e:
            code = _EXC_TO_ERROR_CODE.get(
                type(e).__name__, "ADMIN_NOT_FOUND",
            )
            _show_admin_error(self, code, f"{e} (错误码: {code})")
            return
        except Exception as e:
            _show_admin_error(
                self, "INTERNAL_ERROR",
                f"删除管理员失败: {e} (错误码: INTERNAL_ERROR)",
            )
            return
        self._refresh_table()
        self._show_status(f"已删除管理员 {username}")


class AdminCreateDialog(QtWidgets.QDialog):
    """创建管理员对话框 (SPEC-002 §3.3 AdminCreateDialog)."""

    def __init__(
        self, parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._saved_username: Optional[str] = None
        self._build_ui()
        self._wire_signals()

    @property
    def saved_username(self) -> Optional[str]:
        """成功创建后返回 username (供父窗口 statusBar 提示)."""
        return self._saved_username

    def _build_ui(self) -> None:
        self.setWindowTitle("新增管理员")
        self.setModal(True)

        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("用户名 (≤ 50 字符)")
        self.username_edit.setMaxLength(50)

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setPlaceholderText("密码 (≥ 6 位)")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_edit.setMaxLength(128)

        form = QtWidgets.QFormLayout()
        form.addRow("用户名*", self.username_edit)
        form.addRow("密码*", self.password_edit)

        self.btn_save = QtWidgets.QPushButton("保存")
        self.btn_cancel = QtWidgets.QPushButton("取消")
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(btn_layout)
        prepare_dialog(self, '新增管理员', '创建可登录本地管理系统的账号。', self.btn_save)

    def _wire_signals(self) -> None:
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_save_clicked(self) -> None:
        """校验非空 + 调 AdminService.create.

        校验顺序 (按 spec 002 §3.3 + §6.1):
            1. username / password 非空 (空 → INTERNAL_ERROR 兜底,
               service 不会拒空 username, dialog 层兜底防垃圾数据)
            2. AdminService.create 真实调用
                - UsernameExists → "USERNAME_EXISTS"
                - PasswordTooShort → "PASSWORD_TOO_SHORT"
                - InternalError (USERNAME_TOO_LONG) → "INTERNAL_ERROR"

        成功后 self.accept() + 记录 saved_username (供父窗口 statusBar).
        """
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            _show_admin_error(
                self, "INTERNAL_ERROR",
                "用户名 / 密码 不能为空 (错误码: INTERNAL_ERROR)",
            )
            return
        try:
            AdminService.create(username=username, password=password)
        except (
            UsernameExists,
            PasswordTooShort,
            InternalError,
        ) as e:
            code = _EXC_TO_ERROR_CODE.get(
                type(e).__name__, "INTERNAL_ERROR",
            )
            _show_admin_error(self, code, f"{e} (错误码: {code})")
            return
        self._saved_username = username
        self.accept()
