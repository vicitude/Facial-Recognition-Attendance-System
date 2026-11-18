"""签到/签退人员管理系统 - 根入口 (SPEC-001-C §0 / T-306).

执行流程:
  1. 读 INI 配置
  2. init_db (建库 + 建表 + seed schedule)
  3. ensure_default 管理员
  4. 弹 LoginDialog
  5. 成功 → MainWindow
  6. app.exec_() 退出后 close_db
"""

import sys

from PyQt5 import QtCore, QtWidgets

from attendance.config import ConfigService
from attendance.db import close_db, init_db
from attendance.services import AdminService
from attendance.ui_login import LoginDialog
from attendance.ui_main import MainWindow
from attendance.ui_theme import apply_theme
from attendance.utils import InternalError


def main() -> int:
    # 1. 配置
    try:
        config = ConfigService.load()
    except Exception as e:
        _critical(f"无法读取配置: {e}")
        return 1

    # 2. 数据库aad
    try:
        init_db(config)
    except Exception as e:
        _critical(f"数据库初始化失败: {e}")
        return 1

    # 3. 默认管理员
    try:
        admin_default = config["admin"]
        AdminService.ensure_default(
            admin_default["default_username"],
            admin_default["default_password"],
        )
    except InternalError as e:
        _critical(f"默认管理员创建失败: {e}")
        return 1

    # 4. Qt 应用 + 登录
    app = _application()
    login = LoginDialog()
    if login.exec_() != QtWidgets.QDialog.Accepted:
        # LoginDialog.closeEvent 会 sys.exit(0), 此分支实际不会到达
        return 0
    if login.admin is None:
        _critical("登录异常: admin 未赋值")
        return 1

    # 5. 主窗口
    window = MainWindow(login.admin)
    window.show()
    exit_code = app.exec_()

    # 6. 关闭数据库
    close_db()
    return exit_code


def _critical(message: str) -> None:
    """严重错误 → 弹 QMessageBox.critical + 写 stderr."""
    print(f"FATAL: {message}", file=sys.stderr)
    try:
        app = _application()
        QtWidgets.QMessageBox.critical(None, "启动失败", message)
    except Exception:
        # 弹窗失败不阻断 stderr
        pass


def _application():
    app = QtWidgets.QApplication.instance()
    if app is None:
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    return app


if __name__ == "__main__":
    sys.exit(main())
