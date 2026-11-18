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
    BlobField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    ForeignKeyField,
    FloatField,
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
    """可配置班次，时间字段均为本地时间。"""

    id = AutoField()
    name = CharField(50, unique=True)
    work_start = TimeField()
    work_end = TimeField()
    check_in_start = TimeField()
    late_end = TimeField()
    check_out_end = TimeField()
    location_name = CharField(100, null=True)
    location_latitude = FloatField(null=True)
    location_longitude = FloatField(null=True)
    location_radius_m = FloatField(null=True)
    duplicate_policy = CharField(20, default="reject")
    is_active = BooleanField(default=True)
    # 兼容旧代码和旧表中的阈值字段；新规则使用显式窗口字段。
    late_threshold_min = IntegerField(default=15)
    early_leave_threshold_min = IntegerField(default=15)
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
    face_image_path = CharField(255, null=True)
    schedule = ForeignKeyField(Schedule, null=True, backref="employees")
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "employees"


class EmployeeSchedule(BaseModel):
    """员工与班次的多对多绑定。"""

    id = AutoField()
    employee = ForeignKeyField(Employee, backref="schedule_bindings", on_delete="CASCADE")
    schedule = ForeignKeyField(Schedule, backref="employee_bindings", on_delete="CASCADE")
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "employee_schedules"
        indexes = ((('employee', 'schedule'), True),)


class FaceTemplate(BaseModel):
    """员工三姿态加密人脸模板，不保存原始照片或明文向量。"""

    id = AutoField()
    employee = ForeignKeyField(Employee, backref="face_templates", on_delete="CASCADE")
    pose = CharField(20)
    ciphertext = BlobField()
    nonce = BlobField()
    format_version = IntegerField(default=1)
    model_version = CharField(100)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "face_templates"
        indexes = ((('employee', 'pose'), True),)


class CheckRecord(BaseModel):
    """打卡记录 (§4.2)."""

    id = AutoField()
    employee = ForeignKeyField(Employee)
    check_timestamp = DateTimeField(default=datetime.now)
    check_type = CharField(10)
    check_date = DateField()
    schedule = ForeignKeyField(Schedule, null=True, backref="check_records", on_delete="SET NULL")
    adjusted_by = ForeignKeyField(Admin, null=True, backref="adjusted_records", on_delete="SET NULL")
    status = CharField(20, default="normal")
    anomaly_reason = CharField(255, null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "check_records"
