"""签到/签退人员管理系统 - 主窗口 (SPEC-001-C §5 MainWindow).

阶段 2 (T-305 部分):
- Tab 0 实时签到 → CheckInTab
- Tab 1 人员管理 → EmployeesTab
- Tab 2 打卡记录 → 占位 (阶段 3 用 RecordsTab 替换)

T-602 增量 (SPEC-002 §3.3):
- 「账户」菜单 + 「修改密码」Action (`action_change_password`)
- 触发 ChangePasswordDialog (self._admin), accept 后 statusBar 提示
"""

from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from attendance.db import close_db
from attendance.models import Admin
from attendance.ui_admins import AdminsTab
from attendance.ui_change_password import ChangePasswordDialog
from attendance.ui_checkin import CheckInTab
from attendance.ui_employees import EmployeesTab
from attendance.ui_records import RecordsTab
from attendance.ui_schedules import SchedulesTab
from attendance.ui_theme import StarBanner, apply_theme, label


class MainWindow(QtWidgets.QMainWindow):
    """主窗口。"""

    APP_TITLE: str = "签到/签退人员管理系统 v1.0.0"
    PASSWORD_HINT: str = "首次登录后请尽快修改密码"

    def __init__(
        self,
        admin: Admin,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._admin = admin
        self._build_ui()
        self._wire_signals()

    # ----------------------------------------------------------
    # UI 构造
    # ----------------------------------------------------------

    def _build_ui(self) -> None:
        self.setWindowTitle(self.APP_TITLE)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        apply_theme(self)

        # 中心 TabWidget (4 个 Tab: T-603 增量 1 个)
        self.tabs = QtWidgets.QTabWidget()
        self.checkin_tab = CheckInTab()
        self.employees_tab = EmployeesTab()
        self.records_tab = RecordsTab()
        self.admins_tab = AdminsTab(self._admin)
        self.schedules_tab = SchedulesTab()

        self.tabs.addTab(self.checkin_tab, "实时签到")
        self.tabs.addTab(self.employees_tab, "人员管理")
        self.tabs.addTab(self.records_tab, "打卡记录")
        self.tabs.addTab(self.admins_tab, "管理员管理")
        self.tabs.addTab(self.schedules_tab, "班次管理")
        self.tabs.tabBar().hide()
        workspace = QtWidgets.QWidget()
        workspace.setObjectName('workspace')
        shell = QtWidgets.QHBoxLayout(workspace)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QtWidgets.QFrame()
        sidebar.setObjectName('sidebar')
        side_layout = QtWidgets.QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 28, 18, 22)
        side_layout.setSpacing(16)
        brand = label('人脸签到', 'brand')
        brand.setWordWrap(False)
        side_layout.addWidget(brand)
        side_layout.addWidget(label('人脸识别 · 人员管理', 'eyebrow'))
        self.navigation = QtWidgets.QListWidget()
        self.navigation.setObjectName('navigation')
        self.navigation.setAccessibleName('主导航')
        self.navigation.addItems(['01   实时签到', '02   人员管理', '03   打卡记录', '04   管理员管理', '05   班次管理'])
        self.navigation.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.navigation.ensurePolished()
        navigation_width = max(self.navigation.fontMetrics().horizontalAdvance(self.navigation.item(index).text()) for index in range(self.navigation.count()))
        sidebar.setFixedWidth(max(240, navigation_width + 80))
        side_layout.addWidget(self.navigation, 1)
        side_layout.addWidget(StarBanner())
        side_layout.addWidget(label('本地运行 · 数据留在此设备', 'eyebrow'))
        shell.addWidget(sidebar)
        content = QtWidgets.QVBoxLayout()
        content.setContentsMargins(24, 24, 24, 16)
        content.setSpacing(16)
        header = QtWidgets.QHBoxLayout()
        heading = QtWidgets.QVBoxLayout()
        heading.addWidget(label('日常管理 / 智能考勤', 'eyebrow'))
        self.page_title = label('实时签到', 'pageTitle')
        heading.addWidget(self.page_title)
        header.addLayout(heading, 1)
        header.addWidget(label(f'管理员 · {self._admin.username}', 'badge'))
        content.addLayout(header)
        content.addWidget(self.tabs, 1)
        shell.addLayout(content, 1)
        self.setCentralWidget(workspace)
        self.navigation.currentRowChanged.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(self._sync_navigation)
        self.navigation.setCurrentRow(0)

        # 底部状态栏
        status_text = (
            f"当前管理员: {self._admin.username} | {self.PASSWORD_HINT}"
        )
        self.statusBar().showMessage(status_text)

        # 菜单
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        self.action_exit = QtWidgets.QAction("退出", self)
        self.action_exit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        file_menu.addAction(self.action_exit)

        # 「账户」菜单 (T-602 增量, SPEC-002 §3.3 MainWindow-账户→修改密码)
        account_menu = menubar.addMenu("账户")
        self.action_change_password = QtWidgets.QAction("修改密码", self)
        account_menu.addAction(self.action_change_password)
        # 「账户 → 管理员管理」 (T-603 增量, 切到 Tab 3)
        self.action_admin_management = QtWidgets.QAction("管理员管理", self)
        account_menu.addAction(self.action_admin_management)
        self.action_liveness = QtWidgets.QAction('三次眨眼活体（试运行）', self)
        self.action_liveness.setCheckable(True)
        self.action_liveness.setChecked(False)
        # 保留属性供兼容调用，设置入口移到管理员管理页。
        self.action_liveness.triggered.connect(self._on_liveness_toggled)
        self.admins_tab.liveness_requested.connect(self._on_liveness_toggled)
        self.admins_tab.color_liveness_requested.connect(self._on_color_liveness_toggled)
        self.admins_tab.color_liveness_ratio_changed.connect(self._on_color_liveness_ratio_changed)

    def _wire_signals(self) -> None:
        self.action_exit.triggered.connect(self._on_exit_triggered)
        self.action_change_password.triggered.connect(
            self._on_change_password_triggered
        )
        self.action_admin_management.triggered.connect(
            self._on_admin_management_triggered
        )

    # ----------------------------------------------------------
    # 槽函数
    # ----------------------------------------------------------

    def _on_liveness_toggled(self, enabled: bool) -> None:
        if not self.checkin_tab.set_liveness_enabled(enabled):
            self.statusBar().showMessage('请先停止识别并关闭相机，再修改活体试运行开关。')
        actual = self.checkin_tab.liveness_enabled
        previous = self.action_liveness.blockSignals(True)
        self.action_liveness.setChecked(actual)
        self.action_liveness.blockSignals(previous)
        self.admins_tab.set_liveness_state(actual)

    def _on_color_liveness_ratio_changed(self, ratio: float) -> None:
        if not self.checkin_tab.set_color_liveness_ratio(ratio):
            self.statusBar().showMessage('彩光合格帧比例必须在 50% 到 100% 之间。')

    def _on_color_liveness_toggled(self, enabled: bool) -> None:
        if not self.checkin_tab.set_color_liveness_enabled(enabled):
            self.statusBar().showMessage('请先停止识别并关闭相机，再修改彩色光试运行开关。')
        self.admins_tab.set_color_liveness_state(self.checkin_tab.color_liveness_enabled)

    def _on_exit_triggered(self) -> None:
        if self.close():
            close_db()
            QtWidgets.QApplication.instance().quit()

    def _sync_navigation(self, index: int) -> None:
        self.navigation.setCurrentRow(index)
        self.page_title.setText(self.tabs.tabText(index))

    def _on_change_password_triggered(self) -> None:
        """「账户 → 修改密码」Action 触发 (SPEC-002 §3.3 MainWindow-账户→修改密码).

        弹出 ChangePasswordDialog, accept 后 statusBar 显示"密码已修改, 下次登录生效".
        dialog 自身不耦合 MainWindow, statusBar 由本槽函数在 result=Accepted 后触发.
        """
        dlg = ChangePasswordDialog(self._admin, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.statusBar().showMessage("密码已修改, 下次登录生效", 5000)

    def _on_admin_management_triggered(self) -> None:
        """「账户 → 管理员管理」Action 触发 (SPEC-002 §3.3 MainWindow-账户→管理员管理).

        切到 Tab 3 (admins_tab), AdminsTab 内部已 _refresh_table().
        """
        self.tabs.setCurrentWidget(self.admins_tab)

    # ----------------------------------------------------------
    # 关闭事件: 释放相机资源
    # ----------------------------------------------------------

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # CheckInTab 持有 cv2.VideoCapture, 需在主窗口关闭时释放
        try:
            if self.checkin_tab._close_camera() is False:  # noqa: SLF001
                event.ignore()
                return
        except Exception:
            pass
        super().closeEvent(event)
