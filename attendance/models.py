"""签到/签退人员管理系统 - 数据模型.

4 个 peewee Model, 字段与 SPEC-001-A §3.4 / §4.2 字段映射表逐字一致:
- Admin: 管理员账号
- Schedule: 班次
- Employee: 员工
- CheckRecord: 打卡记录

表名约定 (v1 决策 010): 全部使用复数形式 (admins / schedules / employees
/ check_records), 与 Spec 文档及 USER_GUIDE.md 描述一致。每个 Model
显式声明 class Meta.table_name, 不依赖 peewee 默认行为 (默认 = 类名小写
单数, 与文档冲突)。AGENTS.md L-016.
"""

from datetime import datetime

from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    MySQLDatabase,
    TimeField,
)


# 占位: 实际 database instance 由 attendance.db.init_db 注入
database = MySQLDatabase(None)


class BaseModel(Model):
    """所有 Model 的基类, 绑定全局 database."""

    class Meta:
        database = database


class Admin(BaseModel):
    """管理员账号 (§4.2)."""

    id = AutoField()
    username = CharField(50, unique=True)
    password_hash = CharField(64)
    is_super = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "admins"


class Schedule(BaseModel):
    """班次 (§4.2)."""

    id = AutoField()
    name = CharField(50, unique=True)
    work_start = TimeField()
    work_end = TimeField()
    late_threshold_min = IntegerField()
    early_leave_threshold_min = IntegerField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "schedules"


class Employee(BaseModel):
    """员工 (§4.2)."""

    employee_id = CharField(6, primary_key=True)
    name = CharField(50)
    department = CharField(50, null=True)
    position = CharField(50, null=True)
    phone = CharField(20, null=True)
    email = CharField(100, null=True)
    face_image_path = CharField(255)
    schedule = ForeignKeyField(Schedule)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "employees"


class CheckRecord(BaseModel):
    """打卡记录 (§4.2)."""

    id = AutoField()
    employee = ForeignKeyField(Employee)
    check_timestamp = DateTimeField(default=datetime.now)
    check_type = CharField(10)
    check_date = DateField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "check_records"
