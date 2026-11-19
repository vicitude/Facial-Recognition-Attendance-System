"""签到/签退人员管理系统 - 数据库初始化.

Database 函数:
- init_db(config): 连接 MySQL, 确保库存在, 建表, 预置 schedule
- get_db(): 返回当前 peewee Database 实例
- close_db(): 关闭连接

启动顺序见 SPEC-001-A §5.1 A-BR-001.
"""

import datetime
from typing import Optional

import peewee
import pymysql

from attendance.utils import DBConnectFailed, InternalError, logger


_db_instance: Optional[peewee.MySQLDatabase] = None


def init_db(config: dict) -> None:
    """连接 MySQL, 确保库存在, 建表, 预置 schedule.

    抛出: DBConnectFailed
    """
    global _db_instance

    db_conf = config["database"]
    db_name = db_conf["database"]
    charset = db_conf["charset"]

    # 第 1 步: 用 pymysql 直连 (不指定 db), 测试可达性 + 建库
    try:
        conn = pymysql.connect(
            host=db_conf["host"],
            port=db_conf["port"],
            user=db_conf["user"],
            password=db_conf["password"],
            charset=charset,
        )
    except pymysql.MySQLError as e:
        raise DBConnectFailed(
            f"无法连接 MySQL {db_conf['host']}:{db_conf['port']}: {e}"
        )

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET {charset} COLLATE {charset}_unicode_ci"
            )
        conn.commit()
    except pymysql.MySQLError as e:
        raise DBConnectFailed(f"无法创建数据库 {db_name}: {e}")
    finally:
        conn.close()

    # 第 2 步: 用 peewee 连接目标库
    real_db = peewee.MySQLDatabase(
        db_name,
        host=db_conf["host"],
        port=db_conf["port"],
        user=db_conf["user"],
        password=db_conf["password"],
        charset=charset,
    )
    _db_instance = real_db

    # 把 database 绑到所有 Model
    from attendance.models import (
        Admin, Schedule, Employee, EmployeeSchedule, FaceTemplate, CheckRecord,
    )

    for model in (Admin, Schedule, Employee, EmployeeSchedule, FaceTemplate, CheckRecord):
        model._meta.database = real_db

    # 第 3 步: 建表 (safe=True, 已存在不报错)
    try:
        real_db.connect(reuse_if_open=True)
        real_db.create_tables(
            [Admin, Schedule, Employee, EmployeeSchedule, FaceTemplate, CheckRecord],
            safe=True,
        )
        # 兼容既有数据库：MySQL 版本不统一，先检查字段再补列。
        schedule_columns = {row[0] for row in real_db.execute_sql("SHOW COLUMNS FROM schedules").fetchall()}
        schedule_defs = {
            "check_in_start": "TIME NULL",
            "late_end": "TIME NULL",
            "check_out_end": "TIME NULL",
            "location_name": "VARCHAR(100) NULL",
            "location_latitude": "DOUBLE NULL",
            "location_longitude": "DOUBLE NULL",
            "location_radius_m": "DOUBLE NULL",
            "duplicate_policy": "VARCHAR(20) NOT NULL DEFAULT 'reject'",
            "is_active": "TINYINT(1) NOT NULL DEFAULT 1",
        }
        for name, definition in schedule_defs.items():
            if name not in schedule_columns:
                real_db.execute_sql(f"ALTER TABLE schedules ADD COLUMN {name} {definition}")
        # 为旧班次填充显式窗口，保留原 work_start/work_end 语义。
        for schedule in Schedule.select():
            changed = {}
            if schedule.check_in_start is None:
                changed["check_in_start"] = (
                    datetime.datetime.combine(datetime.date.today(), schedule.work_start)
                    - datetime.timedelta(minutes=60)
                ).time()
            if schedule.late_end is None:
                changed["late_end"] = schedule.work_start
            if schedule.check_out_end is None:
                changed["check_out_end"] = (
                    datetime.datetime.combine(datetime.date.today(), schedule.work_end)
                    + datetime.timedelta(hours=5)
                ).time()
            if changed:
                Schedule.update(**changed).where(Schedule.id == schedule.id).execute()
        check_columns = {row[0] for row in real_db.execute_sql("SHOW COLUMNS FROM check_records").fetchall()}
        if "status" not in check_columns:
            real_db.execute_sql("ALTER TABLE check_records ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'normal'")
        if "anomaly_reason" not in check_columns:
            real_db.execute_sql("ALTER TABLE check_records ADD COLUMN anomaly_reason VARCHAR(255) NULL")
        if "schedule_id" not in check_columns:
            real_db.execute_sql("ALTER TABLE check_records ADD COLUMN schedule_id INT NULL")
        if "adjusted_by_id" not in check_columns:
            real_db.execute_sql("ALTER TABLE check_records ADD COLUMN adjusted_by_id INT NULL")
    except peewee.DatabaseError as e:
        raise DBConnectFailed(f"建表失败: {e}")

    # 第 4 步: 预置 schedule (若表为空)
    seed = config["schedule_seed"]
    try:
        if Schedule.select().count() == 0:
            Schedule.create(
                name=seed["name"],
                work_start=datetime.time(
                    int(seed["work_start"].split(":")[0]),
                    int(seed["work_start"].split(":")[1]),
                    int(seed["work_start"].split(":")[2]),
                ),
                work_end=datetime.time(
                    int(seed["work_end"].split(":")[0]),
                    int(seed["work_end"].split(":")[1]),
                    int(seed["work_end"].split(":")[2]),
                ),
                check_in_start=datetime.time(
                    int(seed.get("check_in_start", "08:00:00").split(":")[0]),
                    int(seed.get("check_in_start", "08:00:00").split(":")[1]),
                    int(seed.get("check_in_start", "08:00:00").split(":")[2]),
                ),
                late_end=datetime.time(
                    int(seed.get("late_end", seed["work_end"]).split(":")[0]),
                    int(seed.get("late_end", seed["work_end"]).split(":")[1]),
                    int(seed.get("late_end", seed["work_end"]).split(":")[2]),
                ),
                check_out_end=datetime.time(
                    int(seed.get("check_out_end", "23:00:00").split(":")[0]),
                    int(seed.get("check_out_end", "23:00:00").split(":")[1]),
                    int(seed.get("check_out_end", "23:00:00").split(":")[2]),
                ),
                duplicate_policy="reject",
                is_active=True,
                late_threshold_min=seed["late"],
                early_leave_threshold_min=seed["early"],
            )
            logger.info("action=schedule.seed name=%s", seed["name"])
    except peewee.PeeweeException as e:
        raise InternalError(f"预置班次失败: {e}")

    logger.info("action=db.init host=%s database=%s", db_conf["host"], db_name)


def get_db() -> peewee.MySQLDatabase:
    """返回当前 peewee Database 实例."""
    if _db_instance is None:
        raise DBConnectFailed("数据库未初始化, 请先调用 init_db")
    return _db_instance


def close_db() -> None:
    """关闭连接."""
    global _db_instance
    if _db_instance is not None and not _db_instance.is_closed():
        _db_instance.close()
    _db_instance = None
    logger.info("action=db.close")
