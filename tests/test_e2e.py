"""SPEC-001-D 端到端测试 (7 个 TC, 与 spec §2.1 + §7 覆盖矩阵一一对应).

C 层测单一 UI 控件，D 层测管理员登录、管理后台与独立签到窗口的端到端协作。

策略:
- QT_QPA_PLATFORM=offscreen (C 层同款), 不依赖真实显示器.
- cv2.VideoCapture / recognition.recognition / get_name.rec 全部 mock 拦截.
- EmployeeDialog.exec_ / CheckConfirmDialog.exec_ monkeypatch 模拟用户填表+点保存.
- QMessageBox.warning monkeypatch 捕获弹窗内容 (offscreen 下不弹真窗).

约束:
- 严格不修改 conftest.py (G-06 红线)
- 复用 conftest 5 个 fixture: _db_session / _patch_argv / _per_test_reset /
  sample_schedule / face_image (sample_employees 本层未直接用, D07~D10 自己造数据)
- 文件内自管 Qt、默认管理员、签到窗口和管理后台 fixture，以及 _FakeCaptureOk
- 复用 attendance_db, 每 TC 前 _per_test_reset 清表
"""

import sys

import pytest

pytest.importorskip("PyQt5")


# ============================================================
# 平台 / QApplication / admin / main window fixtures
# (与 C 层 test_ui_login.py / test_ui_checkin.py 风格一致)
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    """offscreen 平台必须在 import QtWidgets 前设 (C-01 同款)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    """单例 QApplication (C-01 同款)."""
    from PyQt5 import QtWidgets
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


@pytest.fixture
def default_admin():
    """AdminService.ensure_default + authenticate, 返 admin 实例 (与 test_integration.py 同名 fixture 同实现).

    D05~D11 全用; 与 conftest._per_test_reset 协作 (每 TC 前 Admin 表已清空)。
    """
    from attendance.services import AdminService
    AdminService.ensure_default("admin", "admin123")
    return AdminService.authenticate("admin", "admin123")


@pytest.fixture
def kiosk(app, qtbot):
    from attendance.ui_kiosk import CheckInWindow

    window = CheckInWindow()
    qtbot.addWidget(window)
    return window


@pytest.fixture
def logged_in_main_window(kiosk, default_admin, qtbot):
    """直接创建管理后台，借用独立签到窗口持有的 CheckInTab。"""
    from attendance.ui_main import MainWindow

    window = MainWindow(default_admin, kiosk.checkin_tab)
    qtbot.addWidget(window)
    return window


class _FakeCaptureOk:
    """模拟一个能成功 open + read 0 帧 的 cv2.VideoCapture (C-12 同款)."""

    def __init__(self, *args, **kwargs):
        self._opened = True

    def isOpened(self):
        return self._opened

    def read(self):
        import numpy as np
        return True, np.zeros((480, 640, 3), dtype=np.uint8)

    def release(self):
        self._opened = False


# ============================================================
# D05: 登录 → 主窗口 完整流程
# ============================================================


def test_TC_ATT_D05_e2e_login_to_main(kiosk, default_admin, qtbot):
    """D05: LoginDialog 输入正确账号 → accept → MainWindow 实例化 → 4 个管理页 + statusBar.

    与 C-02 (login accept) + C-05 (main window) 的区别: C 层只测单一组件 accept,
    本 TC 测"login.admin 传递到 MainWindow._admin + statusBar 渲染"端到端链。
    """
    from attendance.ui_login import LoginDialog
    from attendance.ui_main import MainWindow

    dlg = LoginDialog()
    dlg.username_edit.setText("admin")
    dlg.password_edit.setText("admin123")
    dlg._on_login_clicked()
    assert dlg.result() == dlg.Accepted
    assert dlg.admin is not None
    assert dlg.admin.username == "admin"

    # login.admin → MainWindow._admin → statusBar 文本
    main_window = MainWindow(dlg.admin, kiosk.checkin_tab)
    qtbot.addWidget(main_window)
    assert main_window.windowTitle() == MainWindow.APP_TITLE == "考勤管理后台"
    assert main_window.tabs.count() == 4
    assert [main_window.tabs.tabText(i) for i in range(4)] == [
        "人员管理", "打卡记录", "管理员管理", "班次管理",
    ]
    assert "admin" in main_window.statusBar().currentMessage()
    assert "首次登录后请尽快修改密码" in main_window.statusBar().currentMessage()


# ============================================================
# D06: 主窗口 Tab 切换
# ============================================================


def test_TC_ATT_D06_e2e_main_window_tabs(logged_in_main_window):
    """D06: MainWindow 4 tab 索引/标题/实例对应 + 切换 + 退出 action 存在."""
    from attendance.ui_admins import AdminsTab
    from attendance.ui_employees import EmployeesTab
    from attendance.ui_records import RecordsTab
    from attendance.ui_schedules import SchedulesTab

    main_window = logged_in_main_window

    assert main_window.tabs.count() == 4
    assert isinstance(main_window.tabs.widget(0), EmployeesTab)
    assert isinstance(main_window.tabs.widget(1), RecordsTab)
    assert isinstance(main_window.tabs.widget(2), AdminsTab)
    assert isinstance(main_window.tabs.widget(3), SchedulesTab)

    assert main_window.tabs.widget(0) is main_window.employees_tab
    assert main_window.tabs.widget(1) is main_window.records_tab
    assert main_window.tabs.widget(2) is main_window.admins_tab
    assert main_window.tabs.widget(3) is main_window.schedules_tab

    # 切换 tab
    for i in range(4):
        main_window.tabs.setCurrentIndex(i)
        assert main_window.tabs.currentIndex() == i

    # 退出 action 存在
    assert main_window.action_exit.text() == "退出管理"
    assert main_window.action_exit.shortcut().toString() == "Ctrl+Q"


# ============================================================
# D07: 跨 3 Tab 端到端 (新增 → 识别 → 记录)
# ============================================================


def test_TC_ATT_D07_e2e_employees_add_checkin_records(
    monkeypatch, sample_schedule, face_image, logged_in_main_window, kiosk
):
    """D07: 后台新增员工 → 独立签到窗口识别打卡 → 后台显示记录。

    跨两个窗口的端到端流程：
    - cv2.VideoCapture → _FakeCaptureOk (避免依赖真实相机)
    - recognition.recognition → 返 1 个 box
    - get_name.rec → 返 "100001" (face_datasets/100001.jpg 的 basename, 无扩展名,
                              模拟新版 ui_checkin 接收的 face_datasets 文件名)
    - EmployeeService.get_by_face_image_name → 直接返测试员工
      (face_image fixture 用 tmp_path 绝对路径, 不匹配 face_datasets/ 前缀;
       e2e 不依赖 service 真实查询, 简化 DB 状态)
    - EmployeeDialog.exec_ → fake_exec 填表后返 Accepted
    - CheckConfirmDialog.exec_ → fake_exec 触发 btn_in.click() 后返 Accepted

    与 C-07 (employees add) + C-12 (checkin open) + C-16 (records refresh) 的区别:
    C 层各自测单一 tab, 本 TC 测 3 tab 数据流贯通。

    P1 修正 (决策 008 v2 + D07 改造): 原测试假设 get_name.rec 返 employee_id ("200007"),
    新版 ui_checkin 走 face_image_path 反查 (EmployeeService.get_by_face_image_name),
    依赖关系从 employee_id 改成 face_image 文件名. 本 TC mock get_by_face_image_name 直接
    返测试员工, 不依赖真实 face_image_path 路径格式 (face_image fixture 是绝对 tmp 路径).
    """
    import cv2
    import numpy as np
    import get_name
    import recognition
    from PyQt5 import QtWidgets

    from attendance.models import Employee
    from attendance.services import EmployeeService
    from attendance.ui_checkin import CheckConfirmDialog
    from attendance.ui_employees import EmployeeDialog
    from attendance.utils import EmployeeNotFound

    main_window = logged_in_main_window

    # 1. mock camera
    monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureOk)

    # 2. mock recognition.recognition 返 1 个 box [x1,y1,x2,y2,score,cls,label]
    fake_box = [10, 20, 100, 200, 0.95, 0, "face"]
    monkeypatch.setattr(
        recognition, "recognition", lambda frame: [fake_box],
    )

    # 3. mock get_name.rec 返 "100001" (face_datasets/100001.jpg 的 basename, 无扩展名)
    # 新设计 (决策 008 v2 + D07 改造): get_name.rec 返 face_datasets/ 文件 basename,
    # ui_checkin 走 EmployeeService.get_by_face_image_name 反查 DB (按 face_image_path 前缀匹配).
    monkeypatch.setattr(
        get_name, "rec", lambda frame, box: "100001",
    )

    # 3.5 mock EmployeeService.get_by_face_image_name → 直接返测试员工
    # 注: face_image fixture 写真实文件到 tmp_path/100001.jpg (绝对路径),
    # EmployeeService._validate_face_image_path 已被 monkeypatch 放宽 regex
    # (conftest face_image fixture), 但路径仍是绝对路径, 不会匹配
    # face_datasets/100001.* 前缀. e2e 测试不依赖 service 真实查询, mock 直接返.
    def fake_get_by_face_image_name(name):
        return EmployeeService.get("200007")
    monkeypatch.setattr(
        EmployeeService, "get_by_face_image_name",
        staticmethod(fake_get_by_face_image_name),
    )

    # 4. mock EmployeeDialog.exec_ → 填好表单 + 触发 _on_save 后返 Accepted
    def fake_emp_exec(self):
        # 模拟用户填 3 个必填字段 (工号/姓名/人脸照片路径)
        self.employee_id_edit.setText("200007")
        self.name_edit.setText("集成B")
        self.face_path_edit.setText(face_image)
        # schedule_combo 默认 currentIndex=0 = sample_schedule.id (_build_ui 时填充)
        # 直接调 _on_save (替代 btn_save.click() 走完整 signal 链路) 触发
        # EmployeeService.create + self.accept() 设 result=Accepted
        self._on_save()
        return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(EmployeeDialog, "exec_", fake_emp_exec)

    # 5. mock CheckConfirmDialog.exec_ → 触发 _confirm("check_in") 后返 Accepted
    def fake_confirm_exec(self):
        # _confirm("check_in") 内部: CheckService.create_record → recorded.emit → accept
        # 替代 btn_in.click() 走 signal 链路, 行为等价但更稳
        self._confirm("check_in")
        return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(CheckConfirmDialog, "exec_", fake_confirm_exec)

    # ----- 触发端到端流程 -----
    # Step 1: 后台切到人员管理 → 点新增
    main_window.tabs.setCurrentIndex(0)
    main_window.employees_tab.btn_add.click()

    # Step 2: 在独立签到窗口触发识别
    zero_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    kiosk.checkin_tab._do_recognition(zero_frame)

    # Step 3: 后台切到打卡记录 → 刷新
    main_window.tabs.setCurrentIndex(1)
    main_window.records_tab._refresh_table()

    # ----- 断言 -----
    from attendance.models import CheckRecord, Employee

    # 员工已创建
    emp = Employee.get_by_id("200007")
    assert emp.name == "集成B"
    assert emp.face_image_path == face_image
    assert emp.schedule_id == sample_schedule.id

    # 打卡记录已写入 1 条 check_in
    assert CheckRecord.select().where(
        CheckRecord.employee_id == "200007"
    ).count() == 1
    rec = CheckRecord.get(CheckRecord.employee_id == "200007")
    assert rec.check_type == "check_in"

    # EmployeesTab 表格显示 1 行
    assert main_window.employees_tab.table.rowCount() == 1
    assert main_window.employees_tab.table.item(0, 0).text() == "200007"
    assert main_window.employees_tab.table.item(0, 1).text() == "集成B"

    # RecordsTab 表格显示 1 行
    assert main_window.records_tab.table.rowCount() == 1
    assert main_window.records_tab.table.item(0, 0).text() == "200007"
    assert main_window.records_tab.table.item(0, 1).text() == "集成B"


# ============================================================
# D08: 打开/关闭相机端到端
# ============================================================


def test_TC_ATT_D08_e2e_checkin_camera_open_close(monkeypatch, kiosk):
    """D08: 签到窗口打开/关闭相机，校验相机、定时器和状态栏。"""
    import cv2

    tab = kiosk.checkin_tab
    monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureOk)

    # 初始: 相机未打开
    assert tab._camera is None
    assert tab._timer is None
    assert tab.btn_open.text() == "打开相机"
    assert tab.btn_start.isEnabled() is False
    assert tab.btn_stop.isEnabled() is False

    # 打开
    tab.btn_open.click()
    assert tab._camera is not None
    assert tab._camera.isOpened()
    assert tab._timer is not None
    assert tab._timer.isActive()
    assert tab.btn_open.text() == "关闭相机"
    assert tab.btn_start.isEnabled() is True
    assert "相机已打开" in kiosk.statusBar().currentMessage()

    # 关闭
    tab.btn_open.click()
    assert tab._camera is None or not tab._camera.isOpened()
    assert tab._timer is None or not tab._timer.isActive()
    assert tab.btn_open.text() == "打开相机"
    assert tab.btn_start.isEnabled() is False
    assert tab.btn_stop.isEnabled() is False
    assert "相机已关闭" in kiosk.statusBar().currentMessage()


# ============================================================
# D09: 识别 "unknown" → 不打卡
# ============================================================


def test_TC_ATT_D09_e2e_checkin_recognition_unknown(
    monkeypatch, kiosk
):
    """D09: get_name.rec 返 'unknown' → 弹 QMessageBox.warning '未识别', 不打卡.

    与 C-13 (open camera fail) 的区别: C-13 测相机硬件失败, 本 TC 测识别
    流程中"特征比对 unknown" 软失败, 验证 CheckService.create_record 未被调用。
    """
    import get_name
    import numpy as np
    import recognition
    from PyQt5 import QtWidgets

    tab = kiosk.checkin_tab

    # 捕获 QMessageBox.warning
    captured: dict = {}

    def fake_warning(parent, title, text, *args, **kwargs):
        captured["title"] = title
        captured["text"] = text
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", staticmethod(fake_warning),
    )

    fake_box = [10, 20, 100, 200, 0.95, 0, "face"]
    monkeypatch.setattr(
        recognition, "recognition", lambda frame: [fake_box],
    )
    monkeypatch.setattr(
        get_name, "rec", lambda frame, box: "unknown",
    )

    # 触发识别
    zero_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tab._do_recognition(zero_frame)

    # 断言: 弹 warning + 无 CheckRecord
    assert captured["title"] == "未识别"
    assert "人脸不在库中" in captured["text"]
    from attendance.models import CheckRecord
    assert CheckRecord.select().count() == 0

    # P1 缺口: 任务 1 修复后, 未识别分支必须停识别 + 状态栏反馈,
    # 防止 L255/L270/L278 弹窗后 30ms timer 循环再弹 (决策 005 L-005 关联).
    assert tab.flag_recognition is False, "未识别后必须停止识别"
    assert tab.btn_start.isEnabled() is True, "停止识别后开始按钮应重新启用"
    assert tab.btn_stop.isEnabled() is False, "停止识别后停止按钮应禁用"
    assert "未识别" in kiosk.statusBar().currentMessage(), \
        "状态栏应反馈未识别 + 提示"


# ============================================================
# D10: 识别结果不在员工库 → 不打卡
# ============================================================


def test_TC_ATT_D10_e2e_checkin_face_not_in_db(
    monkeypatch, kiosk
):
    """D10: get_name.rec 返 '200099' (face_datasets 有但 db 无此 employee) → warning, 不打卡.

    与 D09 的区别: D09 是"unknown" (face_datasets 都没命中), 本 TC 是"face_datasets
    命中但 employee 表无此工号", 走 EmployeeNotFound 分支。
    """
    import get_name
    import numpy as np
    import recognition
    from PyQt5 import QtWidgets

    tab = kiosk.checkin_tab

    captured: dict = {}

    def fake_warning(parent, title, text, *args, **kwargs):
        captured["title"] = title
        captured["text"] = text
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "warning", staticmethod(fake_warning),
    )

    fake_box = [10, 20, 100, 200, 0.95, 0, "face"]
    monkeypatch.setattr(
        recognition, "recognition", lambda frame: [fake_box],
    )
    monkeypatch.setattr(
        get_name, "rec", lambda frame, box: "200099",
    )

    zero_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tab._do_recognition(zero_frame)

    # 断言: 弹 warning + 工号在文本中 + 无 CheckRecord
    assert captured["title"] == "未识别"
    assert "200099" in captured["text"]
    assert "不在员工库中" in captured["text"]
    from attendance.models import CheckRecord
    assert CheckRecord.select().count() == 0

    # P1 缺口: 任务 1 修复后, 未识别分支必须停识别 + 状态栏反馈,
    # 防止 L255/L270/L278 弹窗后 30ms timer 循环再弹 (决策 005 L-005 关联).
    assert tab.flag_recognition is False, "未识别后必须停止识别"
    assert tab.btn_start.isEnabled() is True, "停止识别后开始按钮应重新启用"
    assert tab.btn_stop.isEnabled() is False, "停止识别后停止按钮应禁用"
    assert "未识别" in kiosk.statusBar().currentMessage(), \
        "状态栏应反馈未识别 + 提示"


# ============================================================
# D11: 管理后台退出不释放相机，签到窗口关闭才释放
# ============================================================


def test_TC_ATT_D11_e2e_kiosk_close_releases_camera(
    monkeypatch, kiosk, logged_in_main_window
):
    """D11: 退出管理不影响签到窗口；关闭签到窗口释放相机和定时器。"""
    import cv2
    from PyQt5 import QtGui

    main_window = logged_in_main_window
    tab = kiosk.checkin_tab
    monkeypatch.setattr(cv2, "VideoCapture", _FakeCaptureOk)

    tab.btn_open.click()
    camera = tab._camera
    assert camera is not None and camera.isOpened()
    assert tab._timer is not None and tab._timer.isActive()

    kiosk.show()
    main_window.show()
    main_window.action_exit.trigger()
    assert not main_window.isVisible()
    assert kiosk.isVisible()
    assert tab.window() is kiosk
    assert tab._camera is camera and camera.isOpened()
    assert tab._timer is not None and tab._timer.isActive()

    # 直接触发 closeEvent，避免依赖 offscreen 下未显示窗口的 close 行为。
    event = QtGui.QCloseEvent()
    kiosk.closeEvent(event)
    assert event.isAccepted()
    assert tab._camera is None
    assert not camera.isOpened()
    assert tab._timer is None
    assert tab.btn_open.text() == "打开相机"


# ============================================================
# E11: 端到端改密 + 新密码 login 成功 + 旧密码 AuthFailed
# ============================================================


def test_TC_ATT_E11_e2e_change_password_full_flow(
    kiosk, default_admin, monkeypatch, qtbot,
):
    """E11: 端到端改密完整流程 (SPEC-002 §7 TC-ATT-E11 + REQ-E-D-01).

    流程:
    1. 触发「账户→修改密码」菜单 → ChangePasswordDialog 弹窗
    2. 填旧="admin123" 新="newpass456" 确认="newpass456"
    3. dialog accept → AdminService.change_password 真实调用 → DB 改密生效
    4. 验证新密码 "newpass456" → AdminService.authenticate 成功
    5. 验证旧密码 "admin123" → AdminService.authenticate 抛 AuthFailed

    与 E-01 (test_TC_ATT_E01_change_password_success) 的区别:
    E-01 测 ChangePasswordDialog 本身交互 + statusBar,
    本 TC 测"改密生效 + 持久化"端到端契约 (DB 真实改了 + 新旧密码鉴权结果).
    spec §7 描述"close dialog + 重新构造 MainWindow + LoginDialog 走新密码 login",
    本 TC 简化为直接用 AdminService.authenticate (等价于新建 MainWindow + LoginDialog,
    MainWindow 不持有 admin 状态, 仅 DB 持久化即可).

    覆盖: REQ-E-D-01.
    """
    from attendance.services import AdminService
    from attendance.ui_change_password import ChangePasswordDialog
    from attendance.ui_main import MainWindow
    from attendance.utils import AuthFailed
    from PyQt5 import QtWidgets

    main_window = MainWindow(default_admin, kiosk.checkin_tab)
    qtbot.addWidget(main_window)

    # 准备 mock ChangePasswordDialog 实例 (沿用 test_ui_change_password.py E-01 模式)
    dlg = ChangePasswordDialog(default_admin, parent=main_window)
    # 不 qtbot.addWidget(dlg): 见 L-005 教训, monkeypatch 走 exec_ 后 Qt
    # 端 C++ 对象已删, teardown 再 close RuntimeError
    dlg.old_password_edit.setText("admin123")
    dlg.new_password_edit.setText("newpass456")
    dlg.confirm_password_edit.setText("newpass456")

    # mock ChangePasswordDialog 引用 → 返 setup 好的 dlg
    monkeypatch.setattr(
        "attendance.ui_main.ChangePasswordDialog",
        lambda *args, **kwargs: dlg,
    )
    # mock dlg.exec_ 走 _on_confirm_clicked (L-005 教训: 保留内部槽函数调用)
    def fake_exec():
        dlg._on_confirm_clicked()
        return dlg.result()
    monkeypatch.setattr(dlg, "exec_", fake_exec)
    # mock QMessageBox.warning no-op (成功路径不弹, 留 hook 防误弹)
    warning_calls: list = []
    def fake_warning(*args, **kwargs):
        warning_calls.append((args, kwargs))
        return QtWidgets.QMessageBox.Ok
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", fake_warning)

    # 触发完整路径
    main_window._on_change_password_triggered()

    # 断言 1: dialog accept + statusBar 提示
    assert dlg.result() == QtWidgets.QDialog.Accepted
    assert "密码已修改" in main_window.statusBar().currentMessage()
    # 断言 2: 无 warning (成功路径)
    assert len(warning_calls) == 0

    # 断言 3: DB 端新密码能 login (等价于"重新构造 MainWindow + LoginDialog 走新密码 login 成功")
    fresh = AdminService.authenticate("admin", "newpass456")
    assert fresh is not None
    assert fresh.username == "admin"

    # 断言 4: DB 端旧密码 AuthFailed (等价于"旧密码 login 抛 AuthFailed")
    with pytest.raises(AuthFailed):
        AdminService.authenticate("admin", "admin123")
