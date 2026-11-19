"""管理员凭设置码注册及登录后更换设置码。"""

from typing import Optional

from PyQt5 import QtWidgets

from attendance.services import AdminService
from attendance.ui_theme import prepare_dialog
from attendance.utils import AuthFailed, InternalError, UsernameExists


class RegistrationDialog(QtWidgets.QDialog):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.saved_username: Optional[str] = None
        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setMaxLength(50)
        self.password_edit = QtWidgets.QLineEdit()
        self.confirmation_edit = QtWidgets.QLineEdit()
        self.code_edit = QtWidgets.QLineEdit()
        for field in (self.code_edit, self.password_edit, self.confirmation_edit):
            field.setEchoMode(QtWidgets.QLineEdit.Password)
            field.setMaxLength(128)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()

        form = QtWidgets.QFormLayout()
        form.addRow('管理员设置码', self.code_edit)
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
        prepare_dialog(self, '凭设置码注册', '注册的账号有完整管理权限，创建后需要重新登录。', self.create_button, 500)
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._create)
        self.cancel_button.clicked.connect(self.reject)
        self.finished.connect(self._clear_passwords)

    def _clear_passwords(self) -> None:
        self.code_edit.clear()
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
            admin = AdminService.register_with_code(self.code_edit.text(), username, password)
        except AuthFailed:
            self._show_error('设置码不正确。')
            return
        except UsernameExists:
            self._show_error('用户名已被使用。')
            return
        except InternalError:
            self._show_error('创建失败，请检查数据库连接后重试。')
            return
        self.saved_username = admin.username
        self.accept()


class ChangeRegistrationCodeDialog(QtWidgets.QDialog):
    def __init__(self, admin_id: int, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._admin_id = admin_id
        self.password_edit = QtWidgets.QLineEdit()
        self.code_edit = QtWidgets.QLineEdit()
        self.confirmation_edit = QtWidgets.QLineEdit()
        for field in (self.password_edit, self.code_edit, self.confirmation_edit):
            field.setEchoMode(QtWidgets.QLineEdit.Password)
        self.code_edit.setMaxLength(128)
        self.confirmation_edit.setMaxLength(128)
        form = QtWidgets.QFormLayout()
        form.addRow('你的管理员密码', self.password_edit)
        form.addRow('新设置码（至少 12 个字符）', self.code_edit)
        form.addRow('确认新设置码', self.confirmation_edit)
        self.error_label = QtWidgets.QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.save_button = QtWidgets.QPushButton('更换')
        self.cancel_button = QtWidgets.QPushButton('取消')
        self.cancel_button.setAutoDefault(False)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(buttons)
        prepare_dialog(self, '更换设置码', '更换后旧码立即失效，已有管理员账号不受影响。', self.save_button, 500)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        self.finished.connect(self._clear_fields)

    def _clear_fields(self) -> None:
        for field in (self.password_edit, self.code_edit, self.confirmation_edit):
            field.clear()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _save(self) -> None:
        password = self.password_edit.text()
        code = self.code_edit.text()
        if not password:
            self._show_error('请输入你的管理员密码。')
            return
        if len(code) < 12 or not code.strip():
            self._show_error('新设置码至少需要 12 个字符，且不能全为空白。')
            return
        if code != self.confirmation_edit.text():
            self._show_error('两次输入的设置码不一致。')
            return
        try:
            AdminService.change_registration_code(self._admin_id, password, code)
        except AuthFailed:
            self._show_error('管理员密码不正确或账号无权更换设置码。')
            return
        except InternalError:
            self._show_error('更换失败：请使用不同于当前设置码的新值，并确认数据库连接正常。')
            return
        self.accept()
