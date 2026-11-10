"""SPEC-001-D 集成测试 (4 个 TC, 与 spec §2.1 + §7 覆盖矩阵一一对应).

与 B 层 18 个单元测试的关系: 集成测试不复测 B 层已覆盖的单一 Service 路径,
而是跨 Service 协作 (Schedule→Employee→CheckRecord + Admin 改密全流程).

约束:
- 严格不修改 conftest.py (G-06 红线)
- 复用 conftest 6 个 fixture: _db_session / _patch_argv / _per_test_reset /
  sample_schedule / face_image / sample_employees
- 文件内自管 1 个 fixture (default_admin), 仅供 D03 使用
- 复用 attendance_db, 每 TC 前 _per_test_reset 清表 (保留 Schedule)

P1 缺口补全 (共 13 处, review 编号 1-13):
- D01: 1 (fixture 一致性) / 2 (外键代理) / 3 (返回值一致性) / 4 (check_date)
- D02: 5 (Schedule 不受影响) / 6 (CheckRecord 清干净) / 7 (二次删抛错)
- D03: 8 (错误旧密码) / 9 (新密码 < 6)
- D04: 10 (employee_id 过滤) / 11 (check_type 过滤) / 12 (date_from==date_to) / 13 (空结果集)
"""

from datetime import date, datetime, time, timedelta

import pytest

from attendance.models import CheckRecord, Employee, Schedule
from attendance.services import (
    AdminService,
    CheckService,
    EmployeeService,
    ScheduleService,
)
from attendance.utils import (
    AuthFailed,
    DateRangeInvalid,
    EmployeeHasRecords,
    EmployeeNotFound,
    PasswordTooShort,
)


# ============================================================
# D 层文件内 fixture (不进 conftest.py, G-06 红线)
# ============================================================


@pytest.fixture
def default_admin():
    """调 AdminService.ensure_default("admin", "admin123") 1 次, 返回 admin 实例.

    D03 使用; 与 conftest._per_test_reset 协作 (每 TC 前 Admin 表已清空,
    ensure_default 才会真正插入 1 条)。
    """
    AdminService.ensure_default("admin", "admin123")
    return AdminService.authenticate("admin", "admin123")


# ============================================================
# D01: Schedule → Employee → CheckRecord 全链路
# ============================================================


def test_TC_ATT_D01_service_chain_schedule_employee_check(
    sample_schedule, face_image
):
    """D01: 跨 Service 协作打通 Schedule→Employee→CheckRecord 数据流.

    与 B-04 (单 Employee create) + B-12 (单 check_in create) 的区别:
    B 层只测单一 Service 单步, 本 TC 验证多 Service 串联后 DB 状态符合预期。
    """
    # 1. 取 schedule (跨 Service 取参, 验证 ScheduleService 可用)
    schedules = ScheduleService.list_all()
    assert len(schedules) >= 1
    schedule = schedules[0]
    # P1-1: fixture 一致性护栏 (sample_schedule 与 list_all()[0] 应是同一个 seed 班次)
    assert schedule.id == sample_schedule.id

    # 2. 建 employee (用 keyword 形式, 与 services.py 签名一致)
    emp = EmployeeService.create(
        employee_id="200001",
        name="集成A",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=schedule.id,
    )
    assert emp.employee_id == "200001"

    # 3. 写 2 条打卡记录 (check_in + check_out)
    CheckService.create_record("200001", "check_in")
    CheckService.create_record("200001", "check_out")

    # 4. 断言: DB 状态符合预期
    db_emp = Employee.get_by_id("200001")
    assert db_emp.name == "集成A"
    # P1-3: create 返回值 vs 重新查询一致性 (peewee 缓存 vs 真实 DB)
    assert db_emp.id == emp.id

    records = list(
        CheckRecord.select()
        .where(CheckRecord.employee == db_emp)
        .order_by(CheckRecord.check_timestamp.desc())
    )
    assert len(records) == 2
    # 不强制 records[0/1] 顺序 (避免依赖 Windows 15ms 时钟精度)
    types = {r.check_type for r in records}
    assert types == {"check_in", "check_out"}
    # P1-2: 外键代理字段正确 (CheckRecord.employee ForeignKey → employee_id)
    assert all(r.employee_id == "200001" for r in records)
    # P1-4: check_date 字段由 service 写为 today, 与 DB DateField 一致
    assert all(r.check_date == date.today() for r in records)


# ============================================================
# D02: 删除约束级联
# ============================================================


def test_TC_ATT_D02_delete_cascade_constraint(face_image, sample_schedule):
    """D02: 有 CheckRecord 的 employee 不可删, 清记录后可删, 删后 Schedule 不变.

    与 B-10 (无 check_records delete) + B-11 (有 check_records delete) 的区别:
    B-10/B-11 测单一 Service, 本 TC 测"先失败再成功"的完整级联清理流程 +
    二次删除抛错 + 外键无 CASCADE 副作用。
    """
    # 1. 建 employee + 1 条 check_in
    EmployeeService.create(
        employee_id="200002",
        name="集成B",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    CheckService.create_record("200002", "check_in")

    # 2. 第一次 delete 抛 EmployeeHasRecords
    with pytest.raises(EmployeeHasRecords):
        EmployeeService.delete("200002")

    # 3. employee 仍存在
    assert Employee.select().where(
        Employee.employee_id == "200002"
    ).exists()

    # 4. 清 CheckRecord (绕过 service, 直接用 ORM, 模拟运维级清理)
    emp = Employee.get_by_id("200002")
    CheckRecord.delete().where(CheckRecord.employee == emp).execute()
    # P1-6: 清理彻底性 (无残留 CheckRecord)
    assert CheckRecord.select().count() == 0

    # 5. 第二次 delete 成功
    EmployeeService.delete("200002")

    # 6. employee 不存在
    assert not Employee.select().where(
        Employee.employee_id == "200002"
    ).exists()
    # P1-5: 删除不影响 Schedule (peewee ForeignKeyField 默认无 CASCADE)
    assert Schedule.select().count() == 1
    # P1-7: 二次删除抛 EmployeeNotFound (B-09 只测 update, delete 二次未覆盖)
    with pytest.raises(EmployeeNotFound):
        EmployeeService.delete("200002")


# ============================================================
# D03: 管理员改密
# ============================================================


def test_TC_ATT_D03_admin_change_password(default_admin):
    """D03: 改密后旧密码失效, 新密码生效, 错误旧密码/短新密码不改密.

    与 B-17 (authenticate 成功) + B-18 (authenticate 失败) 的区别:
    B 层只测 auth 单点, 本 TC 测"auth 成功 → 改密 → auth 失败 → auth 成功"全流程
    + "错误旧密码抛 AuthFailed" + "短新密码抛 PasswordTooShort" 两个失败路径。

    注意: AdminService.change_password 签名是 (admin_id, old, new), 不是
    (username, old, new); spec §2.1 已修正为本签名。
    """
    # 1. default_admin fixture 已 ensure_default + authenticate 成功
    assert default_admin.username == "admin"
    aid = default_admin.id

    # 2. P1-8: 错误旧密码抛 AuthFailed (当前密码 admin123, 旧密码 wrongpass 错)
    with pytest.raises(AuthFailed):
        AdminService.change_password(aid, "wrongpass", "newpass789")

    # 3. P1-9: 新密码 < 6 抛 PasswordTooShort (旧密码对, 新密码 "123" 太短)
    with pytest.raises(PasswordTooShort):
        AdminService.change_password(aid, "admin123", "123")

    # 4. 验证 P1-8 + P1-9 失败路径"不"改密: 旧密码 admin123 仍生效, newpass789/123 未生效
    assert AdminService.authenticate("admin", "admin123").id == aid
    with pytest.raises(AuthFailed):
        AdminService.authenticate("admin", "newpass789")
    with pytest.raises(AuthFailed):
        AdminService.authenticate("admin", "123")

    # 5. 主路径: 改密 (admin_id 是 int, 按位置传)
    AdminService.change_password(aid, "admin123", "newpass456")

    # 6. 旧密码 auth 抛 AuthFailed
    with pytest.raises(AuthFailed):
        AdminService.authenticate("admin", "admin123")

    # 7. 新密码 auth 成功
    new_admin = AdminService.authenticate("admin", "newpass456")
    assert new_admin.id == aid
    assert new_admin.username == "admin"


# ============================================================
# D04: 跨天记录查询
# ============================================================


def test_TC_ATT_D04_list_records_date_range(face_image, sample_schedule):
    """D04: 跨天日期范围查询返回正确列表, 反向范围抛 DateRangeInvalid.

    与 B-15 (按日期范围查询) + B-16 (反向范围) 的区别:
    B 层只测 CheckService 单点, 本 TC 测"建 employee + 跨天记录 + 范围查询"全链路
    + employee_id 过滤 + check_type 过滤 + 端点相等 + 空结果集 4 个边界。
    """
    # 1. 建 employee
    EmployeeService.create(
        employee_id="200004",
        name="集成D",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    emp = Employee.get_by_id("200004")

    # 2. 直接用 ORM 造 3 条跨天记录
    #    (CheckService.create_record 只能造当天, 历史数据需绕过 service, 同 B-15 手法)
    today = date.today()
    yesterday = today - timedelta(days=1)

    CheckRecord.create(
        employee=emp,
        check_type="check_in",
        check_timestamp=datetime.combine(yesterday, time(9, 0)),
        check_date=yesterday,
    )
    CheckRecord.create(
        employee=emp,
        check_type="check_out",
        check_timestamp=datetime.combine(yesterday, time(18, 0)),
        check_date=yesterday,
    )
    CheckRecord.create(
        employee=emp,
        check_type="check_in",
        check_timestamp=datetime.combine(today, time(9, 0)),
        check_date=today,
    )

    # 3. 范围查询返回 3 条降序
    records = CheckService.list_records(
        date_from=yesterday,
        date_to=today,
        employee_id="200004",
    )
    assert len(records) == 3
    # 降序: records[i].check_timestamp >= records[i+1].check_timestamp
    for i in range(len(records) - 1):
        assert records[i].check_timestamp >= records[i + 1].check_timestamp
    # P1-10: employee_id 过滤有效性 (无其他 employee 记录混入)
    assert all(r.employee_id == "200004" for r in records)

    # P1-11: check_type 过滤 (check_in 应 2 条: 昨天 9:00 + 今天 9:00)
    records_in = CheckService.list_records(
        date_from=yesterday,
        date_to=today,
        employee_id="200004",
        check_type="check_in",
    )
    assert len(records_in) == 2
    assert all(r.check_type == "check_in" for r in records_in)

    # P1-12: 端点相等 (date_from == date_to == today, 应返回 1 条)
    records_today_only = CheckService.list_records(
        date_from=today,
        date_to=today,
        employee_id="200004",
    )
    assert len(records_today_only) == 1
    assert records_today_only[0].check_date == today

    # P1-13: 空结果集 (查明天, 范围内无数据)
    tomorrow = today + timedelta(days=1)
    records_future = CheckService.list_records(
        date_from=tomorrow,
        date_to=tomorrow,
        employee_id="200004",
    )
    assert len(records_future) == 0

    # 4. 反向范围抛 DateRangeInvalid
    with pytest.raises(DateRangeInvalid):
        CheckService.list_records(
            date_from=today,
            date_to=yesterday,
            employee_id="200004",
        )
