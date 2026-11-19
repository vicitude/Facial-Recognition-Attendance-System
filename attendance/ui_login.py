"""管理员设置入口的账号密码登录对话框。"""

from typing import Optional

from PyQt5 import QtWidgets

from attendance.models import Admin
from attendance.services import AdminService
from attendance.ui_utils import show_error
from attendance.ui_theme import StarBanner, prepare_dialog
from attendance.utils import AuthFailed


class LoginDialog(QtWidgets.QDialog):
    """登录对话框。"""

    APP_TITLE: str = "管理员登录"
    RegisterRequested = 2

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.admin: Optional[Admin] = None  # 登录成功后赋值
        self._build_ui()
        self._wire_signals()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(self.APP_TITLE)

        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("用户名")

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        self.login_button = QtWidgets.QPushButton("登录")

        form = QtWidgets.QFormLayout()
        form.addRow("用户名", self.username_edit)
        form.addRow("密码", self.password_edit)

        self.cancel_button = QtWidgets.QPushButton("取消")
        self.cancel_button.setAutoDefault(False)
        buttons = QtWidgets.QHBoxLayout()
        self.register_button = QtWidgets.QPushButton('凭设置码注册')
        self.register_button.setAutoDefault(False)
        self.register_button.hide()
        buttons.addWidget(self.register_button)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.login_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(StarBanner())
        layout.addLayout(form)
        layout.addLayout(buttons)
        prepare_dialog(self, '管理员登录', '登录后进入考勤管理后台。', self.login_button, 500)
        self.login_button.setDefault(True)

    def _wire_signals(self) -> None:
        self.login_button.clicked.connect(self._on_login_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self.register_button.clicked.connect(lambda: self.done(self.RegisterRequested))

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _on_login_clicked(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        if not username or not password:
            show_error(
                self,
                "AUTH_FAILED",
                "用户名和密码不能为空 (错误码: AUTH_FAILED)",
            )
            return
        try:
            self.admin = AdminService.authenticate(username, password)
        except AuthFailed:
            show_error(
                self,
                "AUTH_FAILED",
                "用户名或密码错误 (错误码: AUTH_FAILED)",
            )
            return
        self.accept()
