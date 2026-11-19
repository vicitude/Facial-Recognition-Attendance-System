"""当面交付时，在空管理员库中设置账号，不建立登录会话。"""

from typing import Optional

from PyQt5 import QtWidgets

from attendance.services import AdminService
from attendance.ui_theme import prepare_dialog
from attendance.utils import InternalError, UsernameExists


class FirstAdminDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.saved_username: Optional[str] = None
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setMaxLength(50)
        self.password_edit = QtWidgets.QLineEdit()
        self.confirmation_edit = QtWidgets.QLineEdit()
        for field in (self.password_edit, self.confirmation_edit):
            field.setEchoMode(QtWidgets.QLineEdit.Password)
            field.setMaxLength(128)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QtWidgets.QFormLayout()
        form.addRow('用户名', self.username_edit)
        form.addRow('密码（至少 12 个字符）', self.password_edit)
        form.addRow('确认密码', self.confirmation_edit)

        self.create_button = QtWidgets.QPushButton('创建账号')
        self.cancel_button = QtWidgets.QPushButton('取消')
        self.cancel_button.setAutoDefault(False)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.create_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        prepare_dialog(self, '设置首个管理员', '请由客户负责人现场设置。创建后需要重新登录。', self.create_button, 500)
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._create)
        self.cancel_button.clicked.connect(self.reject)
        self.finished.connect(self._clear_passwords)

    def _clear_passwords(self) -> None:
        self.password_edit.clear()
        self.confirmation_edit.clear()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _create(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username:
            self._show_error('请输入用户名。')
            return
        if len(password) < 12 or not password.strip():
            self._show_error('密码至少需要 12 个字符，且不能全为空白。')
            return
        if password != self.confirmation_edit.text():
            self._show_error('两次输入的密码不一致。')
            return
        try:
            admin = AdminService.create_first(username, password)
        except UsernameExists:
            admin = None
        except InternalError:
            self._show_error('创建失败，请检查数据库连接后重试。')
            return
        if admin is None:
            self._show_error('管理员已设置，请取消后重新点击齿轮登录。')
            return
        self.saved_username = admin.username
        self.accept()
