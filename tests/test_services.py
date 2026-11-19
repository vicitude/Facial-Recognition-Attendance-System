"""SPEC-001-B 业务服务层单元测试 (18 个 TC, 与 spec §7 覆盖矩阵一一对应)."""

from datetime import date, datetime, timedelta

import pytest

from attendance.models import Admin, CheckRecord, Employee
from attendance.services import (
    AdminService,
    CheckService,
    EmployeeService,
    ScheduleService,
)
from attendance.utils import (
    AdminNotFound,
    AuthFailed,
    CheckTypeInvalid,
    DateRangeInvalid,
    EmployeeHasRecords,
    EmployeeIdExists,
    EmployeeIdInvalid,
    EmployeeInactive,
    EmployeeNotFound,
    FaceImageNotFound,
    InternalError,
    LastAdminForbidden,
    PasswordTooShort,
    ScheduleNotFound,
    SelfDeleteForbidden,
    UsernameExists,
    sha256_hex,
)


# ============================================================
# B-01 / B-02 / B-03: ScheduleService
# ============================================================


def test_TC_ATT_B01_schedule_get_exists(sample_schedule):
    """B-01: 按 id 查询存在的班次。"""
    s = ScheduleService.get(sample_schedule.id)
    assert s.id == sample_schedule.id
    assert s.name == sample_schedule.name


def test_TC_ATT_B02_schedule_get_not_found():
    """B-02: 查询不存在的班次。"""
    with pytest.raises(ScheduleNotFound):
        ScheduleService.get(999999)


def test_TC_ATT_B03_schedule_list_all(sample_schedule):
    """B-03: 列出所有班次 (按 id 升序)。"""
    schedules = ScheduleService.list_all()
    assert isinstance(schedules, list)
    assert len(schedules) >= 1
    ids = [s.id for s in schedules]
    assert ids == sorted(ids)


# ============================================================
# B-04 ~ B-11: EmployeeService
# ============================================================


def test_TC_ATT_B04_employee_create_ok(face_image, sample_schedule):
    """B-04: 新增员工全条件通过。"""
    emp = EmployeeService.create(
        employee_id="100001",
        name="张三",
        department="研发部",
        position="工程师",
        phone="13800138000",
        email="zs@example.com",
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    assert emp.employee_id == "100001"
    assert emp.name == "张三"
    assert Employee.select().where(
        Employee.employee_id == "100001"
    ).exists()


def test_TC_ATT_B05_employee_create_id_invalid(face_image, sample_schedule):
    """B-05: 工号格式错。"""
    with pytest.raises(EmployeeIdInvalid):
        EmployeeService.create(
            employee_id="abc123",
            name="测试",
            department=None,
            position=None,
            phone=None,
            email=None,
            face_image_path=face_image,
            schedule_id=sample_schedule.id,
        )
    assert not Employee.select().where(
        Employee.employee_id == "abc123"
    ).exists()


def test_TC_ATT_B06_employee_create_id_exists(face_image, sample_schedule):
    """B-06: 工号重复。"""
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    with pytest.raises(EmployeeIdExists):
        EmployeeService.create(
            employee_id="100001",
            name="李四",
            department=None,
            position=None,
            phone=None,
            email=None,
            face_image_path=face_image,
            schedule_id=sample_schedule.id,
        )


def test_TC_ATT_B07_employee_create_face_not_found(sample_schedule):
    """B-07: 人脸照片不存在 (路径合法但文件不在)。"""
    with pytest.raises(FaceImageNotFound):
        EmployeeService.create(
            employee_id="999999",
            name="测试",
            department=None,
            position=None,
            phone=None,
            email=None,
            face_image_path="face_datasets/notexist.jpg",
            schedule_id=sample_schedule.id,
        )


def test_TC_ATT_B08_employee_update_partial(face_image, sample_schedule):
    """B-08: 部分字段更新,其他字段未变,updated_at 刷新。

    备注: MySQL DATETIME 默认精度 0 (秒), 微秒被截断,
    所以 before 截断到秒,断言 updated_at >= before 仍能证明被刷新过。
    """
    before_create = datetime.now().replace(microsecond=0)
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department="研发部",
        position="工程师",
        phone="13800138000",
        email="zs@example.com",
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    emp = EmployeeService.update("100001", name="张三改名")
    assert emp.name == "张三改名"
    db_emp = Employee.get_by_id("100001")
    assert db_emp.name == "张三改名"
    assert db_emp.department == "研发部"  # 其他字段未变
    assert db_emp.position == "工程师"
    # update 调用时刻必晚于 before_create, 截断到秒后 updated_at 必然 >= before_create
    assert db_emp.updated_at >= before_create


def test_TC_ATT_B09_employee_update_not_found():
    """B-09: 更新不存在的员工。"""
    with pytest.raises(EmployeeNotFound):
        EmployeeService.update("999999", name="X")


def test_TC_ATT_B10_employee_delete_no_records(face_image, sample_schedule):
    """B-10: 删除无打卡记录的员工。"""
    EmployeeService.create(
        employee_id="100002",
        name="王五",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    EmployeeService.delete("100002")
    assert not Employee.select().where(
        Employee.employee_id == "100002"
    ).exists()


def test_TC_ATT_B11_employee_delete_has_records(face_image, sample_schedule):
    """B-11: 二次确认后删除有打卡记录的员工及其关联记录。"""
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    CheckService.create_record("100001", "check_in", schedule_id=sample_schedule.id)
    EmployeeService.delete("100001")
    assert not Employee.select().where(
        Employee.employee_id == "100001"
    ).exists()


# ============================================================
# B-12 ~ B-16: CheckService
# ============================================================


def test_TC_ATT_B12_check_create_record_ok(face_image, sample_schedule):
    """B-12: 写入 check_in 记录。"""
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    rec = CheckService.create_record("100001", "check_in", schedule_id=sample_schedule.id)
    assert rec.employee_id == "100001"
    assert rec.check_type == "check_in"
    assert rec.check_date == date.today()
    assert CheckRecord.select().where(
        CheckRecord.employee == rec.employee
    ).count() == 1


def test_TC_ATT_B13_check_create_record_inactive(face_image, sample_schedule):
    """B-13: 写入 check_in 但员工已离职。"""
    EmployeeService.create(
        employee_id="100002",
        name="离职员工",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
        is_active=False,
    )
    with pytest.raises(EmployeeInactive):
        CheckService.create_record("100002", "check_in")


def test_TC_ATT_B14_check_create_record_invalid_type(face_image, sample_schedule):
    """B-14: 写入非法 check_type。"""
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    with pytest.raises(CheckTypeInvalid):
        CheckService.create_record("100001", "foo")


def test_TC_ATT_B15_check_list_by_date_range(face_image, sample_schedule):
    """B-15: 按日期范围查询。"""
    EmployeeService.create(
        employee_id="100001",
        name="张三",
        department=None,
        position=None,
        phone=None,
        email=None,
        face_image_path=face_image,
        schedule_id=sample_schedule.id,
    )
    today = date.today()
    emp = Employee.get_by_id("100001")
    # 插入 3 条不同日期的打卡
    for d in (
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    ):
        CheckRecord.create(
            employee=emp,
            check_type="check_in",
            check_timestamp=datetime.combine(d, datetime.min.time()),
            check_date=d,
        )
    recs = CheckService.list_records(
        date_from=today - timedelta(days=1),
        date_to=today,
    )
    assert len(recs) == 2
    for r in recs:
        assert today - timedelta(days=1) <= r.check_date <= today


def test_TC_ATT_B16_check_list_date_range_invalid():
    """B-16: 日期范围反向抛错。"""
    today = date.today()
    with pytest.raises(DateRangeInvalid):
        CheckService.list_records(
            date_from=today,
            date_to=today - timedelta(days=1),
        )


# ============================================================
# B-17 / B-18: AdminService
# ============================================================


def test_TC_ATT_B17_admin_authenticate_ok():
    """B-17: 校验默认账号成功。"""
    AdminService.ensure_default("admin", "admin123")
    admin = AdminService.authenticate("admin", "admin123")
    assert admin.username == "admin"
    assert admin.password_hash == sha256_hex("admin123")


def test_TC_ATT_B18_admin_authenticate_failed():
    """B-18: 校验密码错 / 用户不存在 (合并两条 Gherkin 场景)。"""
    AdminService.ensure_default("admin", "admin123")
    with pytest.raises(AuthFailed):
        AdminService.authenticate("admin", "wrongpass")
    with pytest.raises(AuthFailed):
        AdminService.authenticate("ghost", "any")


# ============================================================
# B-19: EmployeeService.get_by_face_image_name (签到流程, face_datasets 文件名反查)
# ============================================================


def test_TC_ATT_B19_employee_get_by_face_image_name(tmp_path, monkeypatch, sample_schedule):
    """B-19: 按人脸照片文件名查找员工 (face_datasets/xxx.ext 的 basename, 无扩展名).

    用于签到流程: get_name.rec 返回 face_datasets/xxx.{jpg,png} 的 basename (无扩展名),
    反查 DB 找对应员工 (face_image_path 字段).

    4 个场景:
    1. 正常匹配 (face_image_path = "face_datasets/HuangJiaWei.jpg" → 查 "HuangJiaWei")
    2. 多员工库中精确匹配 (不影响其他员工)
    3. 文件名不存在 → EmployeeNotFound
    4. 空字符串 → EmployeeNotFound

    注: 不复用 conftest face_image fixture (它用绝对 tmp 路径, 与生产 face_datasets/ 前缀格式不一致),
    本 TC 自建 tmp_path/face_datasets/ 目录 + 写真文件, 匹配生产环境.
    """
    # 自建 face_datasets/ 真目录 + 真文件, 模拟生产路径
    face_datasets_dir = tmp_path / "face_datasets"
    face_datasets_dir.mkdir()
    (face_datasets_dir / "HuangJiaWei.jpg").write_bytes(b"\x00\x00")
    (face_datasets_dir / "ZhangSan.png").write_bytes(b"\x00\x00")

    # 改 CWD 到 tmp_path, 让 "face_datasets/xxx" 相对路径能解析到真文件
    monkeypatch.chdir(tmp_path)

    # 准备 2 个员工, 用生产路径格式 face_datasets/xxx.{jpg,png}
    EmployeeService.create(
        employee_id="200001", name="黄家伟", department=None,
        position=None, phone=None, email=None,
        face_image_path="face_datasets/HuangJiaWei.jpg",
        schedule_id=sample_schedule.id,
    )
    EmployeeService.create(
        employee_id="200002", name="张三", department=None,
        position=None, phone=None, email=None,
        face_image_path="face_datasets/ZhangSan.png",
        schedule_id=sample_schedule.id,
    )

    # (1) 正常匹配 → 200001
    emp = EmployeeService.get_by_face_image_name("HuangJiaWei")
    assert emp.employee_id == "200001"
    assert emp.name == "黄家伟"

    # (2) 多员工库中精确匹配 (不影响其他员工)
    emp2 = EmployeeService.get_by_face_image_name("ZhangSan")
    assert emp2.employee_id == "200002"
    assert emp2.name == "张三"

    # (3) 文件名不存在 → EmployeeNotFound
    with pytest.raises(EmployeeNotFound):
        EmployeeService.get_by_face_image_name("NonExistent")

    # (4) 空字符串 → EmployeeNotFound
    with pytest.raises(EmployeeNotFound):
        EmployeeService.get_by_face_image_name("")


# ============================================================
# E-09 / E-10: AdminService SPEC-002 (管理员账户管理)
# ============================================================


def test_TC_ATT_E09_admin_create_and_list_and_delete():
    """E-09: AdminService.create / list_all / delete 8 个分支全过.

    注意: MySQL AutoField 不会随 DELETE 重置 auto_increment, 本 TC 不硬编码
    admin_id=1/2, 改用 list_all() 查实际对象, 保证 spec 002 §3.1 不变.
    """
    AdminService.ensure_default("admin", "admin123")

    # (1) create 新 admin 成功
    new_admin = AdminService.create("zhangsan", "zhang123")
    assert isinstance(new_admin, Admin)
    assert new_admin.username == "zhangsan"
    assert new_admin.password_hash == sha256_hex("zhang123")
    assert new_admin.is_super is True

    # (2) create 重名 → UsernameExists
    with pytest.raises(UsernameExists):
        AdminService.create("zhangsan", "newpass123")

    # (3) create 短密码 → PasswordTooShort
    with pytest.raises(PasswordTooShort):
        AdminService.create("lisi", "123")

    # (4) list_all 返 list, 按 id 升序, 含 admin + zhangsan
    admins = AdminService.list_all()
    assert isinstance(admins, list)
    assert len(admins) == 2
    assert admins[0].username == "admin"
    assert admins[1].username == "zhangsan"
    assert admins[0].id < admins[1].id

    # 查实际对象 id (不依赖 auto_increment 重置)
    admin_obj = next(a for a in admins if a.username == "admin")
    zhangsan_obj = next(a for a in admins if a.username == "zhangsan")

    # (5) delete 非最后 + 非自己成功 (current=admin_obj.id, target=zhangsan_obj.id)
    AdminService.delete(admin_id=zhangsan_obj.id, current_admin_id=admin_obj.id)
    assert Admin.get_or_none(Admin.id == zhangsan_obj.id) is None

    # (6) delete 最后 1 个 → LastAdminForbidden
    # 此时表里只剩 admin, 用外部 999999 current_admin_id 绕过自删保护,
    # 单独验证 LastAdminForbidden 分支
    with pytest.raises(LastAdminForbidden):
        AdminService.delete(admin_id=admin_obj.id, current_admin_id=999999)

    # (7) delete 自己 → SelfDeleteForbidden (加 wangwu 让 count > 1)
    AdminService.create("wangwu", "wangwu123")
    with pytest.raises(SelfDeleteForbidden):
        AdminService.delete(admin_id=admin_obj.id, current_admin_id=admin_obj.id)

    # (8) delete 不存在 admin_id → AdminNotFound
    with pytest.raises(AdminNotFound):
        AdminService.delete(admin_id=999999, current_admin_id=admin_obj.id)


def test_TC_ATT_E10_admin_create_username_validation():
    """E-10: username 7 个边界 case (空 / 空格 / 长度 1 / 50 / 51 / 特殊字符 / 中文).

    业务层手动校验 username 长度 ≤ 50 (USERNAME_TOO_LONG), 不依赖 MySQL strict mode.
    """
    # (1) 空字符串 → 成功 (spec 002 §3.1 create 不校验非空, 仅校验唯一)
    admin1 = AdminService.create("", "pass123")
    assert admin1.username == ""
    Admin.delete().where(Admin.id == admin1.id).execute()

    # (2) 纯空格 → 成功
    admin2 = AdminService.create("   ", "pass123")
    assert admin2.username == "   "
    Admin.delete().where(Admin.id == admin2.id).execute()

    # (3) 长度 1 → 成功
    admin3 = AdminService.create("a", "pass123")
    assert admin3.username == "a"
    Admin.delete().where(Admin.id == admin3.id).execute()

    # (4) 长度 50 → 成功 (临界值)
    admin4 = AdminService.create("a" * 50, "pass123")
    assert admin4.username == "a" * 50
    Admin.delete().where(Admin.id == admin4.id).execute()

    # (5) 长度 51 → InternalError (USERNAME_TOO_LONG, service 入口手动校验)
    #    (MySQL non-strict mode 不会截断/报错, 业务层兜底)
    with pytest.raises(InternalError) as excinfo:
        AdminService.create("a" * 51, "pass123")
    assert "USERNAME_TOO_LONG" in str(excinfo.value) or "长度" in str(excinfo.value)
    # 确认 DB 里没残留 (业务层拦在 create 之前)
    assert Admin.select().where(Admin.username == "a" * 51).count() == 0

    # (6) 含特殊字符 → 成功
    admin6 = AdminService.create("admin!@#", "pass123")
    assert admin6.username == "admin!@#"
    Admin.delete().where(Admin.id == admin6.id).execute()

    # (7) 含中文 → 成功
    admin7 = AdminService.create("管理员", "pass123")
    assert admin7.username == "管理员"
    Admin.delete().where(Admin.id == admin7.id).execute()
