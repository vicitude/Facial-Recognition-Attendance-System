# 任务拆解: SPEC-001-A 基础层

> 与 `specs/attendance/01-foundation/spec.md` v1.0.0 配套。

---

## T-001 创建 attendance 子包与入口骨架

- **依赖**: 无
- **前置**: 无
- **产出物**:
  - `attendance/__init__.py`(空, 文件内容仅 `__version__ = "1.0.0"`)
- **关联**: 全部后续任务的物理容器

## T-002 写入 attendance_config.ini 模板与 .gitignore

- **依赖**: T-001
- **前置**: 无
- **产出物**:
  - `attendance_config.ini` 内容:

```ini
; ============================================================
;  签到/签退人员管理系统配置文件
;  此文件包含数据库密码, 严禁提交到 git 仓库
;  .gitignore 已排除此文件
; ============================================================

[database]
host = 127.0.0.1
port = 3306
user = root
password =
database = attendance_db
charset = utf8mb4

[admin]
default_username = admin
default_password = admin123

[schedule_seed]
name = 常规班
work_start = 08:00:00
work_end = 17:00:00
late = 15
early = 15
```

  - `.gitignore` 追加:

```gitignore
# 签到系统配置(包含数据库密码, 不入仓)
attendance_config.ini

# 日志目录
logs/
```

- **关联**: §3.1 ConfigService, §4.1 JSON Schema

## T-003(选做) 在 README 或 AGENTS.md §3 追加依赖说明

- **依赖**: 无
- **前置**: 用户确认 `pip install peewee pymysql`
- **产出物**: 更新 `AGENTS.md` §3.2, 添加:

```text
### 3.2 签到系统依赖

pip install peewee pymysql
```

- **关联**: §9.1 假设

---

## T-101 实现 utils.py

- **依赖**: T-001
- **前置**: 无
- **产出物**: `attendance/utils.py`, 含:
  - `AttendanceError(Exception)` 基类
  - 3 个本子 spec 子类: `INIReadFailed`, `DBConnectFailed`, `InternalError`
  - 11 个预留子类(仅占位, raise 由 B 实现): `AuthFailed`, `PasswordTooShort`, `EmployeeIdInvalid`, `EmployeeIdExists`, `EmployeeNotFound`, `EmployeeHasRecords`, `EmployeeInactive`, `FaceImageNotFound`, `ScheduleNotFound`, `CheckTypeInvalid`, `DateRangeInvalid`
  - `sha256_hex(password: str) -> str`, 内部用 `hashlib.sha256(password.encode('utf-8')).hexdigest()`
  - 模块级 logger: `logger = logging.getLogger(__name__)`, 配置 `logs/attendance_{date}.log`
- **关联**: §3.3 AuthUtils, §6.2 异常类层级
- **覆盖**: TC-ATT-A04, TC-ATT-A05

## T-102 实现 models.py

- **依赖**: T-101
- **前置**: T-001
- **产出物**: `attendance/models.py` 含 §3.4 全部 4 个 Model, 字段名/类型/默认值/必填与 §4.2 逐字一致
- **关联**: §3.4 Models, §4.2 字段映射表
- **覆盖**: TC-ATT-A09, TC-ATT-A10, TC-ATT-A11, TC-ATT-A12

## T-103 实现 config.py

- **依赖**: T-101
- **前置**: T-002
- **产出物**: `attendance/config.py` 含:
  - `ConfigService.INI_PATH = "attendance_config.ini"`
  - `ConfigService.load()`: 用 `configparser` 读 INI, 返回 §4.1 dict;缺键或类型错抛 `INIReadFailed`
  - `ConfigService.ensure_exists()`: 若 INI 不存在, 写入 T-002 模板内容
  - `ConfigService._validate_loaded(d)`: 校验返回 dict 结构
- **关联**: §3.1 ConfigService
- **覆盖**: TC-ATT-A01, TC-ATT-A02, TC-ATT-A03

## T-104 实现 db.py

- **依赖**: T-102, T-103
- **前置**: T-002 (INI 存在)
- **产出物**: `attendance/db.py` 含:
  - 模块级 `_db_instance: Optional[peewee.MySQLDatabase] = None`
  - `init_db(config: dict)`: 
    1. 调 `MySQLDatabase.connect()` 测试连接, 失败抛 `DBConnectFailed`
    2. 调 `db.execute_sql(f"CREATE DATABASE IF NOT EXISTS \`{db_name}\` ...")` 建库
    3. 调 `db.create_tables([Admin, Schedule, Employee, CheckRecord], safe=True)`
    4. 若 `Schedule.select().count() == 0`, 插入 seed (id=1, name='常规班', work_start=time(8,0), work_end=time(17,0), late=15, early=15)
    5. 记录 `logger.info("action=db.init")`
  - `get_db() -> peewee.MySQLDatabase`: 返回 `_db_instance`
  - `close_db()`: `_db_instance.close()`; 记录 `logger.info("action=db.close")`
- **关联**: §3.2 Database, §5.1 A-BR-001
- **覆盖**: TC-ATT-A06, TC-ATT-A07, TC-ATT-A08

---

## 任务依赖图

```text
T-001 ──┬──> T-002 ──> T-103 ──┐
        │                       ├──> T-104
        └──> T-101 ──> T-102 ──┘
        │
        └──> T-003 (独立, AGENTS.md 更新)
```

## 排期

| 阶段 | 任务 | 工时(单人时) |
|------|------|--------------|
| 结构 | T-001, T-002, T-003 | 0.5 |
| 工具 | T-101 | 0.5 |
| 数据 | T-102, T-103, T-104 | 2 |
| **合计** | - | **3** |
