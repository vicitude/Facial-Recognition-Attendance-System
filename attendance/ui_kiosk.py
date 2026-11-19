"""免登录的员工实时签到窗口及管理员入口。"""

from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.ui_checkin import CheckInTab
from attendance.ui_login import LoginDialog
from attendance.ui_main import MainWindow
from attendance.ui_theme import apply_theme, label


class CheckInWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._admin_window: Optional[MainWindow] = None
        self.setWindowTitle('实时签到')
        apply_theme(self)

        workspace = QtWidgets.QWidget()
        workspace.setObjectName('workspace')
        layout = QtWidgets.QVBoxLayout(workspace)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(label('实时签到', 'pageTitle'), 1)
        self.settings_button = QtWidgets.QPushButton('⚙')
        self.settings_button.setAccessibleName('管理员设置')
        self.settings_button.setToolTip('管理员设置')
        header.addWidget(self.settings_button)
        layout.addLayout(header)
        self.checkin_tab = CheckInTab()
        self.checkin_tab.video_label.setMinimumHeight(200)
        self._content_scroll = QtWidgets.QScrollArea()
        self._content_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setWidget(self.checkin_tab)
        layout.addWidget(self._content_scroll, 1)
        self.setCentralWidget(workspace)
        self.settings_button.clicked.connect(self._open_admin)
        self._fit_startup_geometry()

    def _fit_startup_geometry(self) -> None:
        screen = QtWidgets.QApplication.screenAt(QtGui.QCursor.pos())
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            self.resize(1440, 900)
            return
        work_area = screen.availableGeometry()
        # 首次显示前尚无原生边框尺寸，预留标题栏和边框空间。
        title_height = self.style().pixelMetric(QtWidgets.QStyle.PM_TitleBarHeight, None, self)
        size = QtCore.QSize(1440, 900).boundedTo(QtCore.QSize(
            max(1, work_area.width() - 32),
            max(1, work_area.height() - max(56, title_height + 24)),
        ))
        self.resize(size)
        self.move(work_area.center() - QtCore.QPoint(size.width() // 2, size.height() // 2))

    def _open_admin(self) -> None:
        if self._admin_window is not None:
            return
        tab = self.checkin_tab
        if (tab._camera is not None or tab.flag_recognition or tab._color_camera_lease is not None):
            if not tab._close_camera():
                return

        dialog = LoginDialog(self)
        try:
            result = dialog.exec_()
            admin = dialog.admin
        finally:
            dialog.password_edit.clear()
            dialog.deleteLater()
        if result != QtWidgets.QDialog.Accepted or admin is None:
            return

        window = MainWindow(admin, tab, parent=self)
        window.setWindowFlag(QtCore.Qt.Window, True)
        window.setWindowModality(QtCore.Qt.WindowModal)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.destroyed.connect(self._clear_admin_window)
        self._admin_window = window
        window.show()

    def _clear_admin_window(self) -> None:
        self._admin_window = None

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._admin_window is not None or not self.checkin_tab._close_camera():
            event.ignore()
            return
        super().closeEvent(event)
