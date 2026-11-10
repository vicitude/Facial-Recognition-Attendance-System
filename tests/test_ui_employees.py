"""SPEC-001-C 阶段 2 - 人员管理 Tab 烟测 (TC-ATT-C05 ~ C11).

策略:
- 用 pytest-qt + offscreen 平台, 不依赖真实显示器.
- DB 状态由 conftest._per_test_reset 保证 (每 TC 前清表).
- EmployeeDialog.exec_ 被 mock 为先调 _on_save, 再返回 Accepted/Rejected,
  避免模态阻塞 pytest.
- QMessageBox.warning/question 通过 monkeypatch 拦截, 不弹真实框.
"""

import pytest

pytest.importorskip("PyQt5")


# offscreen 平台必须在 import QtWidgets 前设
@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    from PyQt5 import QtWidgets
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


# ============================================================
# TC-ATT-C05 ~ C11
# ============================================================


def test_TC_ATT_C05_employees_tab_shows_list(app, sample_employees):
    """C-05: 进入人员 Tab → 表格 6 列, 3 行, 列头逐字一致."""
    from attendance.ui_employees import EmployeesTab

    tab = EmployeesTab()
    assert tab.table.columnCount() == 6
    assert tab.table.rowCount() == 3

    headers = [
        tab.table.horizontalHeaderItem(i).text() for i in range(6)
    ]
    assert headers == ["工号", "姓名", "部门", "职位", "在职", "班次"]

    # 数据行: 100001 / 张三 / 研发部 / 工程师 / 是 / 测试班次
    assert tab.table.item(0, 0).text() == "100001"
    assert tab.table.item(0, 1).text() == "张三"
    assert tab.table.item(0, 2).text() == "研发部"
    assert tab.table.item(0, 3).text() == "工程师"
    assert tab.table.item(0, 4).text() == "是"


def test_TC_ATT_C06_employees_add_ok(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-06: 新增员工 → dialog 接受, 表格新增一行, DB 新增一行."""
    from PyQt5 import QtWidgets
    from attendance.models import Employee
    from attendance.ui_employees import EmployeesTab, EmployeeDialog

    real_init = EmployeeDialog.__init__

    def fake_init(self, parent=None, mode="add", employee=None):
        real_init(self, parent, mode, employee)
        if mode == "add":
            self.employee_id_edit.setText("100099")
            self.name_edit.setText("新增测试")
            self.department_edit.setText("测试部")
            self.position_edit.setText("测试员")
            self.phone_edit.setText("13900139000")
            self.email_edit.setText("t@e.com")
            self.face_path_edit.setText(face_image)

    def fake_exec(self):
        # 模拟用户点保存: 调 _on_save, 然后 accept
        self._on_save()
        return QtWidgets.QDialog.Accepted

    monkeypatch.setattr(EmployeeDialog, "__init__", fake_init)
    monkeypatch.setattr(EmployeeDialog, "exec_", fake_exec)

    tab = EmployeesTab()
    initial_rows = tab.table.rowCount()
    tab.btn_add.click()

    assert Employee.select().where(
        Employee.employee_id == "100099"
    ).exists()
    assert tab.table.rowCount() == initial_rows + 1


def test_TC_ATT_C07_employees_add_invalid_id(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-07: employee_id='abc' 校验失败 → show_error 触发, dialog 保持."""
    from PyQt5 import QtWidgets
    from attendance.models import Employee
    from attendance.ui_employees import EmployeesTab, EmployeeDialog

    captured = {}

    def fake_show_error(parent, error_code, message):
        captured["error_code"] = error_code
        captured["message"] = message

    monkeypatch.setattr(
        "attendance.ui_employees.show_error", fake_show_error,
    )

    real_init = EmployeeDialog.__init__

    def fake_init(self, parent=None, mode="add", employee=None):
        real_init(self, parent, mode, employee)
        if mode == "add":
            self.employee_id_edit.setText("abc")
            self.name_edit.setText("非法测试")
            self.face_path_edit.setText(face_image)

    def fake_exec(self):
        self._on_save()
        return QtWidgets.QDialog.Rejected

    monkeypatch.setattr(EmployeeDialog, "__init__", fake_init)
    monkeypatch.setattr(EmployeeDialog, "exec_", fake_exec)

    tab = EmployeesTab()
    initial_rows = tab.table.rowCount()
    tab.btn_add.click()

    assert captured["error_code"] == "EMPLOYEE_ID_INVALID"
    assert "EMPLOYEE_ID_INVALID" in captured["message"]
    assert not Employee.select().where(
        Employee.employee_id == "abc"
    ).exists()
    # 表格未刷新 (没新增行)
    assert tab.table.rowCount() == initial_rows


def test_TC_ATT_C08_employees_edit_ok(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-08: 选中行 → 编辑 → 字段预填 → 改 name → 保存 → DB 刷新."""
    from PyQt5 import QtWidgets
    from attendance.models import Employee
    from attendance.services import EmployeeService
    from attendance.ui_employees import EmployeesTab, EmployeeDialog

    EmployeeService.create(
        employee_id="100001", name="张三", department="研发部",
        position="工程师", phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )

    real_init = EmployeeDialog.__init__
    captured = {}

    def fake_init(self, parent=None, mode="add", employee=None):
        real_init(self, parent, mode, employee)
        if mode == "edit":
            # 预填验证
            captured["prefilled_id"] = self.employee_id_edit.text()
            captured["prefilled_name"] = self.name_edit.text()
            captured["prefilled_dept"] = self.department_edit.text()
            captured["prefilled_readonly"] = (
                self.employee_id_edit.isReadOnly()
            )
            # 改 name
            self.name_edit.setText("张三改名")

    def fake_exec(self):
        self._on_save()
        return QtWidgets.QDialog.Accepted

    monkeypatch.setattr(EmployeeDialog, "__init__", fake_init)
    monkeypatch.setattr(EmployeeDialog, "exec_", fake_exec)

    tab = EmployeesTab()
    tab.table.selectRow(0)
    tab.btn_edit.click()

    assert captured["prefilled_id"] == "100001"
    assert captured["prefilled_name"] == "张三"
    assert captured["prefilled_dept"] == "研发部"
    assert captured["prefilled_readonly"] is True

    db_emp = Employee.get_by_id("100001")
    assert db_emp.name == "张三改名"
    assert db_emp.department == "研发部"  # 其他字段保留


def test_TC_ATT_C09_employees_delete_ok(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-09: 删除无打卡记录员工 → 表格移除, DB 删除."""
    from PyQt5 import QtWidgets
    from attendance.models import Employee
    from attendance.services import EmployeeService
    from attendance.ui_employees import EmployeesTab

    EmployeeService.create(
        employee_id="100002", name="李四", department=None,
        position=None, phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )

    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        staticmethod(
            lambda *args, **kwargs: QtWidgets.QMessageBox.Yes
        ),
    )

    tab = EmployeesTab()
    initial_rows = tab.table.rowCount()
    tab.table.selectRow(0)
    tab.btn_delete.click()

    assert not Employee.select().where(
        Employee.employee_id == "100002"
    ).exists()
    assert tab.table.rowCount() == initial_rows - 1


def test_TC_ATT_C10_employees_delete_has_records(
    app, monkeypatch, face_image, sample_schedule,
):
    """C-10: 删除有打卡记录员工 → show_error EMPLOYEE_HAS_RECORDS."""
    from PyQt5 import QtWidgets
    from attendance.models import Employee
    from attendance.services import CheckService, EmployeeService
    from attendance.ui_employees import EmployeesTab

    EmployeeService.create(
        employee_id="100001", name="张三", department=None,
        position=None, phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )
    CheckService.create_record("100001", "check_in")

    captured = {}

    def fake_show_error(parent, error_code, message):
        captured["error_code"] = error_code
        captured["message"] = message

    monkeypatch.setattr(
        "attendance.ui_employees.show_error", fake_show_error,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox, "question",
        staticmethod(
            lambda *args, **kwargs: QtWidgets.QMessageBox.Yes
        ),
    )

    tab = EmployeesTab()
    tab.table.selectRow(0)
    tab.btn_delete.click()

    assert captured["error_code"] == "EMPLOYEE_HAS_RECORDS"
    assert "EMPLOYEE_HAS_RECORDS" in captured["message"]
    assert Employee.select().where(
        Employee.employee_id == "100001"
    ).exists()


def test_TC_ATT_C11_employees_search_filters(app, sample_employees):
    """C-11: 搜索 '张' → 表格仅 1 行; 清空恢复 3 行."""
    from attendance.ui_employees import EmployeesTab

    tab = EmployeesTab()
    assert tab.table.rowCount() == 3

    tab.search_edit.setText("张")
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 1).text() == "张三"

    tab.search_edit.setText("")
    assert tab.table.rowCount() == 3


# ============================================================
# TC-ATT-C12 / C13 - 决策 008 v2 P1 回归测试
# ============================================================


def test_TC_ATT_C12_normalize_face_path_unit(app):
    """C-12: 决策 008 v2 单元测试 - _normalize_face_path 各种输入正确归一化.

    锁住 helper 行为:
    1. 已匹配业务层正则 (项目根相对路径) → 不变
    2. back-slash 绝对路径 → 归一化为 forward-slash 相对路径
    3. forward-slash 绝对路径 → 归一化为相对路径
    4. 空字符串 → 不变
    """
    import os
    from attendance.ui_employees import EmployeeDialog

    dlg = EmployeeDialog()

    # 用项目根动态拼绝对路径, 与 helper 内部算法保持 case 一致
    # (避免 Windows 盘符大小写差异导致 relpath 失真)
    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    # 1. 已匹配业务层正则 → 不变 (避免无谓 relpath)
    assert dlg._normalize_face_path(
        "face_datasets/abc.jpg"
    ) == "face_datasets/abc.jpg"

    # 2. back-slash 绝对路径 → 归一化
    abs_back = os.path.join(
        project_root, "face_datasets", "HuangJiaWei.jpg"
    )
    result = dlg._normalize_face_path(abs_back)
    assert result == "face_datasets/HuangJiaWei.jpg"
    assert "\\" not in result  # 全部 forward-slash, 匹配 Service 正则

    # 3. forward-slash 绝对路径 → 归一化
    abs_fwd = abs_back.replace(os.sep, "/")
    assert dlg._normalize_face_path(abs_fwd) == "face_datasets/HuangJiaWei.jpg"

    # 4. 空字符串 → 不变
    assert dlg._normalize_face_path("") == ""


def test_TC_ATT_C13_v2_defensive_normalization(
    app, monkeypatch, sample_schedule,
):
    """C-13: 决策 008 v2 集成回归测试 - 双层防御 (_on_browse + _on_save).

    锁住 v2 行为, 覆盖完整 UI → Service 边界:
    1. _on_browse 收到 QFileDialog 返回的绝对路径 → 归一化后写入编辑框
    2. _on_save 即 _on_browse 漏了 (用户手输入/缓存/旧版本) →
       归一化后传给 EmployeeService, 弹 FACE_IMAGE_NOT_FOUND 的根因被堵死.

    这两个场景覆盖完整路径, 防止 v1 测试盲点 (fixture 直接 setText
    跳过 QFileDialog + 放宽正则) 再次漏掉生产 Bug.
    """
    import os
    from PyQt5 import QtWidgets
    from attendance.services import EmployeeService
    from attendance.ui_employees import EmployeeDialog

    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    abs_path = os.path.join(
        project_root, "face_datasets", "HuangJiaWei.jpg"
    )
    expected = "face_datasets/HuangJiaWei.jpg"

    # 场景 1: _on_browse 即时归一化 (mock QFileDialog 返回绝对路径)
    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (abs_path, "")),
    )
    dlg1 = EmployeeDialog()
    dlg1.btn_browse.click()
    assert dlg1.face_path_edit.text() == expected

    # 场景 2: _on_save 兜底归一化 (mock EmployeeService.create 避免依赖文件存在)
    captured: dict = {}

    def fake_create(*args, **kwargs):
        captured["face_image_path"] = kwargs.get("face_image_path")
        # 阻止实际写库 + 跳过 isfile 检查, 只验证归一化路径

    monkeypatch.setattr(
        EmployeeService, "create", staticmethod(fake_create)
    )

    dlg2 = EmployeeDialog()
    dlg2.employee_id_edit.setText("100099")
    dlg2.name_edit.setText("测试")
    dlg2.face_path_edit.setText(abs_path)  # 用户手输入, 绕过 _on_browse
    dlg2._on_save()
    assert captured["face_image_path"] == expected
