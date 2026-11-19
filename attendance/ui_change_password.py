"""签到/签退人员管理系统 - 修改密码对话框 (SPEC-002 §3.3 ChangePasswordDialog).

T-602 产出物: 弹窗改密, 校验旧密码 + 新密码长度 + 两次新密码一致,
成功后 AdminService.change_password 真实调用, 失败 QMessageBox.warning 弹窗.

设计决策:
- 弹窗标题"修改失败" / 内容按 spec 002 §6.1 表格字面值,
  不走 ui_utils.show_error, 避免修改既有 ui_utils._TITLE_MAP (AGENTS.md §5 红线).
- accept 后状态栏提示由 MainWindow._on_change_password_triggered 外部触发,
  ChangePasswordDialog 不耦合 MainWindow (解耦).
"""

from typing import Optional

from PyQt5 import QtCore, QtWidgets

from attendance.models import Admin
from attendance.services import AdminService
from attendance.ui_theme import prepare_dialog
from attendance.utils import AuthFailed, PasswordTooShort


class ChangePasswordDialog(QtWidgets.QDialog):
    """修改当前管理员密码的弹窗 (SPEC-002 §2.1 Gherkin E-01~E-06)."""

    def __init__(
        self,
        current_admin: Admin,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._current_admin = current_admin
        self._build_ui()
        self._wire_signals()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle("修改密码")
        self.setModal(True)

        title_label = QtWidgets.QLabel("修改密码")
        title_font = self.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(QtCore.Qt.AlignCenter)

        self.old_password_edit = QtWidgets.QLineEdit()
        self.old_password_edit.setPlaceholderText("旧密码")
        self.old_password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        self.new_password_edit = QtWidgets.QLineEdit()
        self.new_password_edit.setPlaceholderText("新密码 (≥ 6 位)")
        self.new_password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        self.confirm_password_edit = QtWidgets.QLineEdit()
        self.confirm_password_edit.setPlaceholderText("确认新密码")
        self.confirm_password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        form = QtWidgets.QFormLayout()
        form.addRow("旧密码", self.old_password_edit)
        form.addRow("新密码", self.new_password_edit)
        form.addRow("确认新密码", self.confirm_password_edit)

        self.btn_confirm = QtWidgets.QPushButton("确定")
        self.btn_cancel = QtWidgets.QPushButton("取消")

        button_box = QtWidgets.QHBoxLayout()
        button_box.addStretch(1)
        button_box.addWidget(self.btn_confirm)
        button_box.addWidget(self.btn_cancel)

        layout = QtWidgets.QVBoxLayout(self)
        title_label.deleteLater()
        layout.addLayout(form)
        layout.addLayout(button_box)
        prepare_dialog(self, '修改密码', '更新当前管理员的登录凭据。', self.btn_confirm)

    def _wire_signals(self) -> None:
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _on_confirm_clicked(self) -> None:
        """校验 + 调 AdminService.change_password.

        校验顺序 (按 spec 002 §2.1 Gherkin E-03~E-05):
            1. 三项均非空 (空 → "AUTH_FAILED" 兜底)
            2. 新密码 = 确认新密码 (不一致 → "PASSWORD_MISMATCH")
            3. AdminService.change_password 真实调用
                - AuthFailed → "AUTH_FAILED" 旧密码错
                - PasswordTooShort → "PASSWORD_TOO_SHORT" 新密码 < 6

        成功后 self.accept(), 状态栏由 MainWindow 外部触发 (解耦).
        """
        old = self.old_password_edit.text()
        new = self.new_password_edit.text()
        confirm = self.confirm_password_edit.text()

        if not old or not new or not confirm:
            QtWidgets.QMessageBox.warning(
                self,
                "修改失败",
                "旧密码 / 新密码 / 确认新密码不能为空 (错误码: AUTH_FAILED)",
            )
            return

        if new != confirm:
            QtWidgets.QMessageBox.warning(
                self,
                "修改失败",
                "两次输入的新密码不一致 (错误码: PASSWORD_MISMATCH)",
            )
            return

        try:
            AdminService.change_password(self._current_admin.id, old, new)
        except AuthFailed:
            QtWidgets.QMessageBox.warning(
                self,
                "修改失败",
                "旧密码错误 (错误码: AUTH_FAILED)",
            )
            return
        except PasswordTooShort:
            QtWidgets.QMessageBox.warning(
                self,
                "修改失败",
                "新密码长度 < 6 (错误码: PASSWORD_TOO_SHORT)",
            )
            return

        self.accept()

    def _on_cancel_clicked(self) -> None:
        self.reject()
