"""签到/签退人员管理系统 - 登录对话框 (SPEC-001-C §3 LoginDialog).

T-301: 启动后弹出, 校验管理员账号, 成功 self.accept() 进入主窗口.
"""

import sys
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.models import Admin
from attendance.services import AdminService
from attendance.ui_utils import show_error
from attendance.utils import AuthFailed


class LoginDialog(QtWidgets.QDialog):
    """登录对话框。"""

    APP_TITLE: str = "签到系统 v1.0.0"

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
        self.setFixedSize(360, 200)

        title_label = QtWidgets.QLabel("签到系统 v1.0.0")
        title_font = QtGui.QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(QtCore.Qt.AlignCenter)

        self.username_edit = QtWidgets.QLineEdit()
        self.username_edit.setPlaceholderText("用户名")

        self.password_edit = QtWidgets.QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QtWidgets.QLineEdit.Password)

        self.login_button = QtWidgets.QPushButton("登录")

        form = QtWidgets.QFormLayout()
        form.addRow("用户名", self.username_edit)
        form.addRow("密码", self.password_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addLayout(form)
        layout.addWidget(self.login_button)

    def _wire_signals(self) -> None:
        self.login_button.clicked.connect(self._on_login_clicked)

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

    # ----------------------------------------------------------
    # 窗口事件
    # ----------------------------------------------------------

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """关闭登录窗口 → 整个进程退出。"""
        sys.exit(0)
