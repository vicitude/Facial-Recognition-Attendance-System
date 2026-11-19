"""SPEC-001-B 测试 fixture.

策略 (S0 安全隔离):
- 必须显式提供测试专用配置，只允许本机 attendance_test_* 数据库
- 每 TC 前清 CheckRecord/Employee/Admin,保留 Schedule (init_db seed 的班次)
- face_image fixture: 用 tmp_path 写真实 .jpg 文件 + monkeypatch 放宽
  FACE_IMAGE_PATH_PATTERN (function scope,TC 结束自动还原,不动业务代码)
- _patch_argv fixture: 临时清 sys.argv 为 [script_name], 避免 recognition.py
  顶部模块级 argparse.parse_args() 读到 pytest 参数后 SystemExit(2).
"""

import datetime
import sys

import pytest

from attendance.config import ConfigService
from attendance.db import close_db, init_db
from attendance.models import Admin, CheckRecord, Employee, Schedule
from attendance.services import EmployeeService
from attendance.test_safety import require_test_config_path, validate_test_database


# ============================================================
# Session 级: 启动时初始化一次库 + 清 sys.argv
# ============================================================


@pytest.fixture(scope="session", autouse=True)
def _db_session():
    original_path = ConfigService.INI_PATH
    try:
        ConfigService.INI_PATH = require_test_config_path()
        config = ConfigService.load()
        validate_test_database(config)
        init_db(config)
        yield
    finally:
        close_db()
        ConfigService.INI_PATH = original_path


@pytest.fixture(autouse=True)
def _patch_argv():
    """recognition.py 顶层调用 argparse.parse_args()(无参 → 走 sys.argv[1:]).
    pytest 跑时 sys.argv[1:] 是 pytest 参数, argparse 不认识会 SystemExit(2).
    此 fixture 把 sys.argv 临时改为 [script_name], 让 argparse 走默认值.
    TC 结束自动还原.
    """
    original = sys.argv
    sys.argv = [original[0]] if original else [""]
    try:
        yield
    finally:
        sys.argv = original


# ============================================================
# Function 级: 每 TC 前清业务表 + 保证 schedule 存在
# ============================================================


@pytest.fixture(autouse=True)
def _per_test_reset():
    """每 TC 前清 CheckRecord/Employee/Admin,Schedule 保留。"""
    CheckRecord.delete().execute()
    Employee.delete().execute()
    Admin.delete().execute()
    if Schedule.select().count() == 0:
        Schedule.create(
            name="测试班次",
            work_start=datetime.time(0, 1, 0),
            work_end=datetime.time(23, 0, 0),
            check_in_start=datetime.time(0, 0, 0),
            late_end=datetime.time(22, 0, 0),
            check_out_end=datetime.time(23, 59, 0),
            duplicate_policy="reject",
            is_active=True,
            late_threshold_min=15,
            early_leave_threshold_min=15,
        )
    Schedule.update(
        work_start=datetime.time(0, 1, 0), work_end=datetime.time(23, 59, 0),
        check_in_start=datetime.time(0, 0, 0), late_end=datetime.time(23, 58, 0),
        check_out_end=datetime.time(23, 59, 0), is_active=True,
    ).execute()
    yield


# ============================================================
# 通用 fixture
# ============================================================


@pytest.fixture
def sample_schedule() -> Schedule:
    """返回 init_db seed 的默认 schedule。"""
    return Schedule.select().get()


@pytest.fixture
def face_image(tmp_path, monkeypatch):
    """创建临时人脸照片 + 临时放宽路径 pattern (测试隔离, 不改业务代码).

    TC 结束 monkeypatch 自动还原 EmployeeService.FACE_IMAGE_PATH_PATTERN
    到原始的 r"^face_datasets/[^/]+\\.(jpg|jpeg|png)$"。
    """
    img = tmp_path / "100001.jpg"
    img.write_bytes(b"\x00\x00")
    monkeypatch.setattr(
        EmployeeService,
        "FACE_IMAGE_PATH_PATTERN",
        r".+\.(jpg|jpeg|png)$",
    )
    return str(img)


@pytest.fixture
def sample_employees(face_image, sample_schedule):
    """3 个 sample 员工 (张三/李四/王五), 供 UI 测试用."""
    EmployeeService.create(
        employee_id="100001", name="张三", department="研发部",
        position="工程师", phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )
    EmployeeService.create(
        employee_id="100002", name="李四", department="市场部",
        position="经理", phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )
    EmployeeService.create(
        employee_id="100003", name="王五", department="运营部",
        position="专员", phone=None, email=None,
        face_image_path=face_image, schedule_id=sample_schedule.id,
    )
    return ["100001", "100002", "100003"]
