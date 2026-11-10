"""SPEC-001-C 阶段 3 - 打卡记录 Tab 烟测 (TC-ATT-C16 ~ C18).

策略:
- 用 pytest-qt + offscreen 平台.
- DB 状态由 conftest._per_test_reset 保证 (每 TC 前清表).
- 历史日期的记录用 CheckRecord.create(...) 直接写 check_date, 绕过 service.
"""

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PyQt5")


@pytest.fixture(scope="session", autouse=True)
def _offscreen_platform():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    from PyQt5 import QtWidgets
    a = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield a


def _create_employee(EmployeeService, face_image, sample_schedule,
                     eid: str, name: str):
    EmployeeService.create(
        employee_id=eid, name=name, department="研发部",
        position="工程师", phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )


def _backdate_record(emp, check_type: str, on_date: date, hour: int = 9):
    """直接写一条 check_date = on_date 的历史记录 (绕开 service)."""
    from attendance.models import CheckRecord
    ts = datetime.combine(on_date, datetime.min.time().replace(hour=hour))
    CheckRecord.create(
        employee=emp, check_type=check_type,
        check_timestamp=ts, check_date=on_date,
    )


# ============================================================
# C-16: 默认 date_from=date_to=today, 显示今日全部
# ============================================================


def test_TC_ATT_C16_records_default_today(
    app, face_image, sample_schedule,
):
    """C-16: 进入记录 Tab, 默认起始/截止=今天, 显示今日全部记录."""
    from attendance.models import Employee
    from attendance.services import CheckService, EmployeeService
    from attendance.ui_records import RecordsTab

    _create_employee(EmployeeService, face_image, sample_schedule,
                     "100001", "张三")
    CheckService.create_record("100001", "check_in")
    CheckService.create_record("100001", "check_out")

    tab = RecordsTab()

    # 默认日期 == 今天
    assert tab.date_from.date().toPyDate() == date.today()
    assert tab.date_to.date().toPyDate() == date.today()

    # 默认 employee / check_type = 全部
    assert tab.employee_combo.currentData() == ""
    assert tab.check_type_combo.currentData() == ""

    # 表格 6 列, 2 行 (今日 2 条)
    assert tab.table.columnCount() == 6
    assert tab.table.rowCount() == 2

    # 类型列渲染为中文
    types_rendered = {
        tab.table.item(r, 5).text() for r in range(2)
    }
    assert types_rendered == {"签到", "签退"}


# ============================================================
# C-17: 改 date_from/date_to 点刷新, 过滤生效
# ============================================================


def test_TC_ATT_C17_records_date_filter(
    app, face_image, sample_schedule,
):
    """C-17: 改起始/截止日期点刷新, 按日期范围过滤生效."""
    from PyQt5 import QtCore
    from attendance.services import CheckService, EmployeeService
    from attendance.ui_records import RecordsTab

    _create_employee(EmployeeService, face_image, sample_schedule,
                     "100001", "张三")

    # 今日 1 条
    CheckService.create_record("100001", "check_in")

    # 2 天前 1 条 (用 timedelta 防跨日)
    from attendance.models import Employee
    two_days_ago = date.today() - timedelta(days=2)
    _backdate_record(
        Employee.get_by_id("100001"), "check_in", two_days_ago,
    )

    tab = RecordsTab()
    # 默认 today 范围 → 仅 1 行
    assert tab.table.rowCount() == 1

    # 改到 [2 天前, 今天] → 2 行
    qd_from = QtCore.QDate.currentDate().addDays(-2)
    qd_to = QtCore.QDate.currentDate()
    tab.date_from.setDate(qd_from)
    tab.date_to.setDate(qd_to)
    tab.btn_refresh.click()
    assert tab.table.rowCount() == 2

    # 改到 [2 天前, 2 天前] → 1 行
    tab.date_from.setDate(qd_from)
    tab.date_to.setDate(qd_from)
    tab.btn_refresh.click()
    assert tab.table.rowCount() == 1


# ============================================================
# C-18: 选 employee / check_type 点刷新, 过滤生效
# ============================================================


def test_TC_ATT_C18_records_employee_type_filter(
    app, face_image, sample_schedule,
):
    """C-18: 选员工 / 类型点刷新, 按 employee + check_type 过滤生效."""
    from attendance.services import CheckService, EmployeeService
    from attendance.ui_records import RecordsTab

    _create_employee(EmployeeService, face_image, sample_schedule,
                     "100001", "张三")
    _create_employee(EmployeeService, face_image, sample_schedule,
                     "100002", "李四")

    # 今日: 张三 2 条 (签到/签退), 李四 1 条 (签到)
    CheckService.create_record("100001", "check_in")
    CheckService.create_record("100001", "check_out")
    CheckService.create_record("100002", "check_in")

    tab = RecordsTab()
    # 默认全选 → 3 行
    assert tab.table.rowCount() == 3

    # ---- 选 employee 100001 (张三) → 2 行 ----
    for i in range(tab.employee_combo.count()):
        if tab.employee_combo.itemData(i) == "100001":
            tab.employee_combo.setCurrentIndex(i)
            break
    tab.btn_refresh.click()
    assert tab.table.rowCount() == 2
    eids = {tab.table.item(r, 0).text() for r in range(2)}
    assert eids == {"100001"}

    # ---- 叠加 check_type = check_in → 1 行 (张三的签到) ----
    for i in range(tab.check_type_combo.count()):
        if tab.check_type_combo.itemData(i) == "check_in":
            tab.check_type_combo.setCurrentIndex(i)
            break
    tab.btn_refresh.click()
    assert tab.table.rowCount() == 1
    assert tab.table.item(0, 0).text() == "100001"
    assert tab.table.item(0, 1).text() == "张三"
    assert tab.table.item(0, 5).text() == "签到"

    # ---- 清空筛选 → 恢复 3 行 (G-04) ----
    tab.btn_clear.click()
    assert tab.table.rowCount() == 3
    assert tab.employee_combo.currentData() == ""
    assert tab.check_type_combo.currentData() == ""
