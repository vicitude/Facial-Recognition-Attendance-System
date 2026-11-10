"""签到/签退人员管理系统 - 工具类.

包含:
- 异常类层级 (AttendanceError 基类 + 14 个业务异常子类)
- sha256_hex 密码哈希函数
- 模块级 logger (写入 logs/attendance_{YYYYMMDD}.log)
"""

import hashlib
import logging
import os
from datetime import datetime


# ============================================================
# 异常类层级 (§6.2)
# ============================================================


class AttendanceError(Exception):
    """所有签到系统业务异常的基类."""


class INIReadFailed(AttendanceError):
    """INI 配置读取失败 (缺失 / 解析错 / 缺键 / 值类型错)."""


class DBConnectFailed(AttendanceError):
    """MySQL 连接失败 / 库无法创建."""


class AuthFailed(AttendanceError):
    """用户名不存在或密码错."""


class PasswordTooShort(AttendanceError):
    """新密码长度 < 6."""


class EmployeeIdInvalid(AttendanceError):
    """employee_id 不匹配 ^\d{6}$."""


class EmployeeIdExists(AttendanceError):
    """employee_id 已存在."""


class EmployeeNotFound(AttendanceError):
    """查/改/删时员工不存在."""


class EmployeeHasRecords(AttendanceError):
    """删员工时存在 check_records."""


class EmployeeInactive(AttendanceError):
    """给 is_active=False 的员工打卡."""


class FaceImageNotFound(AttendanceError):
    """face_image_path 文件不存在或格式错."""


class ScheduleNotFound(AttendanceError):
    """schedule_id 不存在."""


class CheckTypeInvalid(AttendanceError):
    """check_type 不在合法集合 (check_in / check_out / middle)."""


class DateRangeInvalid(AttendanceError):
    """date_from > date_to."""


class InternalError(AttendanceError):
    """未预期异常."""


class UsernameExists(AttendanceError):
    """创建管理员时 username 已被注册."""


class AdminNotFound(AttendanceError):
    """删管理员时 admin_id 不存在."""


class LastAdminForbidden(AttendanceError):
    """删管理员时会锁死系统 (仅剩 1 个 admin)."""


class SelfDeleteForbidden(AttendanceError):
    """删除管理员时试图删自己 (防锁出系统)."""


# ============================================================
# SHA-256 哈希 (§3.3)
# ============================================================


def sha256_hex(password: str) -> str:
    """返回密码字符串的 SHA-256 十六进制 64 字符.

    已知值: sha256_hex('admin123') ==
    '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# ============================================================
# Logger 配置 (§6.3)
# ============================================================


_LOGS_DIR = "logs"


def _build_logger() -> logging.Logger:
    """构造模块 logger, 文件 handler 写入 logs/attendance_{YYYYMMDD}.log."""
    logger = logging.getLogger("attendance")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    if not os.path.isdir(_LOGS_DIR):
        os.makedirs(_LOGS_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(_LOGS_DIR, f"attendance_{today}.log")
    # 5MB 轮转: 启动时若 > 5MB, rename 为 .1
    if os.path.isfile(log_path) and os.path.getsize(log_path) > 5 * 1024 * 1024:
        os.rename(log_path, log_path + ".1")

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = _build_logger()
