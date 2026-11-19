"""签到/签退人员管理系统入口：初始化数据库后直接显示实时签到。"""

import sys

from PyQt5 import QtCore, QtWidgets

from attendance.config import ConfigService
from attendance.db import close_db, init_db
from attendance.ui_kiosk import CheckInWindow
from attendance.ui_theme import apply_theme


def main() -> int:
    # 1. 配置
    try:
        config = ConfigService.load()
    except Exception as e:
        _critical(f"无法读取配置: {e}")
        return 1

    try:
        init_db(config)
    except Exception as e:
        _critical(f"数据库初始化失败: {e}")
        return 1

    try:
        app = _application()
        window = CheckInWindow()
        window.show()
        return app.exec_()
    finally:
        close_db()


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
